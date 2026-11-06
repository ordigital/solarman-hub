"""Optional real-broker test: HUB_TEST_MQTT_PORT=18883 pytest -q."""
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import secrets
from zoneinfo import ZoneInfo
import paho.mqtt.client as paho
import pytest
from solarman_hub.config import AppConfig, ConfigStore, Logger
from solarman_hub.runtime import Runtime
from solarman_hub.mqtt_probe import probe

@pytest.mark.skipif(not os.environ.get('HUB_TEST_MQTT_PORT'), reason='Set HUB_TEST_MQTT_PORT for an isolated real broker')
async def test_real_broker_discovery_state_availability(tmp_path):
    port = int(os.environ['HUB_TEST_MQTT_PORT'])
    config = AppConfig(loggers=[Logger(serial=1234567890,name='Synthetic integration test')])
    config.cloud.enabled=False
    config.mqtt.enabled=True
    config.mqtt.host='127.0.0.1'
    config.mqtt.port=port
    prefix='test_hub_'+secrets.token_hex(4)
    config.mqtt.topic_prefix=prefix
    config.mqtt.discovery_prefix=prefix+'/ha'
    config.mqtt.client_id=prefix
    store=ConfigStore(tmp_path);store.save(config)
    assert (await probe(config.mqtt))['ok']
    runtime=Runtime(tmp_path,tcp_host='127.0.0.1',tcp_port=0)
    queue=asyncio.Queue()
    loop=asyncio.get_running_loop()
    subscriber=paho.Client(paho.CallbackAPIVersion.VERSION2,client_id=prefix+'_subscriber')
    subscriber.on_connect=lambda client,userdata,flags,reason,properties: client.subscribe(prefix+'/#',qos=1)
    subscriber.on_message=lambda client,userdata,message: loop.call_soon_threadsafe(queue.put_nowait,(message.topic,message.payload))
    subscriber.connect_async('127.0.0.1',port);subscriber.loop_start()
    writer=None
    try:
        await runtime.start()
        for _ in range(100):
            if runtime.mqtt.connected:break
            await asyncio.sleep(.05)
        assert runtime.mqtt.connected
        await asyncio.sleep(.2)
        reader,writer=await asyncio.open_connection('127.0.0.1',runtime.tcp_port)
        raw=bytearray(bytes.fromhex((Path(__file__).parent/'fixtures/sofar-report.hex').read_text()))
        now=datetime.now(ZoneInfo(config.server.timezone))
        for offset,value in zip((120,122,124,126,128,130),(now.year-2000,now.month,now.day,now.hour,now.minute,now.second)):
            raw[offset:offset+2]=value.to_bytes(2,'big')
        raw[-2]=sum(raw[1:-2])&255
        writer.write(raw);await writer.drain()
        assert (await asyncio.wait_for(reader.read(256),2))[0]==0xa5
        messages={}
        async with asyncio.timeout(8):
            while len([key for key in messages if key.endswith('/config')])<48 or prefix+'/1234567890/state' not in messages or messages.get(prefix+'/1234567890/availability')!=b'online':
                topic,payload=await queue.get();messages[topic]=payload
        state=json.loads(messages[prefix+'/1234567890/state'])
        assert len(state['values'])==48
        assert state['values']['grid_frequency']==49.98
        configs=[json.loads(value) for key,value in messages.items() if key.endswith('/config')]
        assert all(item['availability_mode']=='all' for item in configs)
        assert len({item['unique_id'] for item in configs})==48
        writer.close();await writer.wait_closed();writer=None
        async with asyncio.timeout(5):
            while True:
                topic,payload=await queue.get()
                if topic==prefix+'/1234567890/availability' and payload==b'offline':break
    finally:
        if writer:writer.close();await writer.wait_closed()
        await runtime.close()
        subscriber.disconnect();await asyncio.to_thread(subscriber.loop_stop)
