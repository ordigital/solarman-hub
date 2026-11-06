import asyncio
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
import time
import pytest
from solarman_hub.config import Storage
from solarman_hub.history import History
from solarman_hub.identity import observed_identity
from solarman_hub.protocol import Frame


def sample(index=0,when=None,revision='one'):
    when=when or time.time()
    return {'serial':123,'sample_time':datetime.fromtimestamp(when+index,tz=timezone.utc).isoformat(),
            'received_at':when+index,'profile':'test','profile_revision':revision,
            'values':{'power':{'name':'Power','value':index,'unit':'W','raw':index}}}


def history(tmp_path,**settings):
    result=History(tmp_path,Storage(**settings),lambda *args,**kwargs:None)
    result.initialize()
    return result


def test_order_pagination_dedup_and_revision(tmp_path):
    store=history(tmp_path)
    now=time.time()
    for index in [3,1,4,2,0]:store.write(sample(index,now))
    store.write(sample(3,now))
    first=store.rows(123,now-1,now+5,2)
    assert [row['values']['power']['value'] for row in first['samples']]==[4,3]
    second=store.rows(123,now-1,now+5,2,first['next_before'])
    assert [row['values']['power']['value'] for row in second['samples']]==[2,1]
    store.write(sample(9,now,revision='two'))
    series=store.series(123,'power','test','one',now-1,now+20)
    assert len(series['points'])==5
    assert all(point['value']!=9 for point in series['points'])
    assert store.rows(999,now-1,now+20)['samples']==[]
    with pytest.raises(ValueError):store.rows(123,now-1,now+20,before=999999)


def test_downsample_keeps_spike_negative_and_gaps(tmp_path):
    store=history(tmp_path)
    now=time.time()
    with store.connect() as db:
        for index in range(200):
            row=sample(index,now)
            row['values']['power']['value']=1000 if index==50 else -100 if index==51 else 1
            store.insert(db,row)
        store.insert(db,sample(2000,now));db.commit()
    result=store.series(123,'power','test','one',now,now+3000,points=16,gap_seconds=900)
    assert len(result['points'])<=16
    assert max(point['value'] for point in result['points'])>=1000
    assert min(point['value'] for point in result['points'])==-100
    assert {point['segment'] for point in result['points']}=={0,1}


def test_retention_uses_received_time_not_logger_clock(tmp_path):
    store=history(tmp_path,history_days=1)
    row=sample();row['sample_time']='2099-01-01T00:00:00+00:00';row['received_at']=time.time()-2*86400
    store.write(row)
    assert store.rows(123,0,3650*86400)['samples']==[]
    old=sample();old['sample_time']='2000-01-01T00:00:00+00:00'
    store.write(old)
    assert len(store.rows(123,946684799,946684801)['samples'])==1


def test_archive_backfill_is_idempotent(tmp_path):
    archive=tmp_path/'archive';archive.mkdir();now=time.time()
    (archive/'measurements.jsonl').write_text(json.dumps(sample(1,now))+'\ninvalid\n'+json.dumps(sample(2,now))+'\n')
    store=history(tmp_path);store.import_archive();store.import_archive()
    assert len(store.rows(123,now,now+3)['samples'])==2


async def test_write_failure_and_full_queue_are_isolated(tmp_path,monkeypatch):
    events=[]
    store=History(tmp_path,Storage(),lambda name,**kwargs:events.append(name))
    await store.start()
    await asyncio.sleep(.03)
    def fail(row):raise sqlite3.OperationalError('disk is full')
    monkeypatch.setattr(store,'write',fail)
    store.submit(sample());await asyncio.wait_for(store.queue.join(),2)
    assert store.last_error and store.dropped==1
    assert 'history_error' in events
    store.task.cancel()
    with pytest.raises(asyncio.CancelledError):await store.task
    store.task=None
    for index in range(300):store.submit(sample(index))
    assert store.queue.qsize()==256 and store.dropped==45
    await store.close()


def test_verified_identity_does_not_guess(tmp_path):
    raw=bytearray(bytes.fromhex((Path(__file__).parent/'fixtures/sofar-report.hex').read_text()))
    assert 'inverter_serial' not in observed_identity(Frame.parse(raw),'192.0.2.2')
    raw[142:158]=b'TESTINVERTER123'.ljust(16,b'\0');raw[-2]=sum(raw[1:-2])&255
    fields=observed_identity(Frame.parse(raw),'192.0.2.2')
    assert fields['inverter_serial']['value']=='TESTINVERTER123'
    assert fields['peer_ip']['source']=='TCP peer'


def test_size_limit_reclaims_physical_files(tmp_path):
    store=history(tmp_path,history_max_mb=8)
    now=time.time()
    with store.connect() as db:
        for index in range(160):
            row=sample(index,now);row['padding']='x'*65536
            store.insert(db,row)
        db.commit()
    store.maintain()
    assert store.size<=8*1024*1024
    rows=store.rows(123,now-1,now+200,limit=200)['samples']
    assert 0<len(rows)<160
    assert rows[0]['values']['power']['value']==159


def test_busy_reader_stops_history_growth(tmp_path):
    store=history(tmp_path,history_max_mb=8)
    now=time.time();store.write(sample(0,now))
    with store.connect() as reader:
        reader.execute('BEGIN')
        reader.execute('SELECT count(*) FROM samples').fetchone()
        with store.connect() as writer:
            writer.execute('PRAGMA wal_autocheckpoint=0')
            for index in range(1,12):
                row=sample(index,now);row['padding']='x'*(1024*1024)
                store.insert(writer,row)
            writer.commit()
        with pytest.raises(OSError,match='storage limit'):
            store.write(sample(12,now))
        assert store.size>8*1024*1024
        reader.rollback()
    store.maintain()
    assert store.size<=8*1024*1024
