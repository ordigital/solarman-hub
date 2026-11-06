import hashlib
from importlib.resources import files
import json
from pathlib import Path
import re
import pytest
from pydantic import ValidationError
from solarman_hub.bundles import Bundle,preview,install
from solarman_hub.guides import CHAPTERS,LANGUAGES,render_guide
from solarman_hub.runtime import Runtime


def bundle(runtime):
    profile=next(iter(runtime.profiles.load().values())).model_dump()
    profile['id']='imported-test-profile'
    return Bundle.model_validate({'bundle_version':1,'verification':'unverified','profile':profile,
        'logger':{'serial':1234567890,'name':'Imported','profile':profile['id']}})


def test_import_is_staged_and_conflicts_are_visible(tmp_path):
    runtime=Runtime(tmp_path)
    value=bundle(runtime)
    summary=preview(runtime,value)
    assert not summary['conflicts'] and summary['verification']=='unverified'
    install(runtime,value)
    assert runtime.active.loggers==[]
    assert runtime.store.load().loggers[0].serial==1234567890
    assert preview(runtime,value)['profile_exists']
    value.profile.fields[0].scale=99
    assert preview(runtime,value)['conflicts']
    with pytest.raises(ValueError):install(runtime,value)


def test_bundle_rejects_secrets_and_mismatched_samples(tmp_path):
    value=bundle(Runtime(tmp_path)).model_dump()
    value['wifi_password']='not-accepted'
    with pytest.raises(ValidationError):Bundle.model_validate(value)
    value.pop('wifi_password')
    value['logger']['serial']=99
    value['sample_hex']=(Path(__file__).parent/'fixtures/sofar-report.hex').read_text()
    with pytest.raises(ValidationError):Bundle.model_validate(value)


def test_localized_guide_chapters_and_commands():
    source=files('solarman_hub').joinpath('guides','en.md').read_text()
    commands=re.findall(r'```[^\n]*\n(.*?)```',source,re.S)
    for language in LANGUAGES:
        guide=render_guide(language)
        assert tuple(item['id'] for item in guide['toc'])==CHAPTERS
        assert 'id="guide-spoofing"' in guide['html']
        assert '<table>' in guide['html'],language
        assert '<code>10001</code>' in guide['html'],language
        translated=files('solarman_hub').joinpath('guides',language+'.md').read_text()
        assert re.findall(r'```[^\n]*\n(.*?)```',translated,re.S)==commands,language
    with pytest.raises(ValueError):render_guide('../en')


def test_firmware_artifact_integrity():
    directory=files('solarman_hub').joinpath('firmware')
    manifest=json.loads(directory.joinpath('manifest.json').read_text())
    assert manifest['chip']=='esp32' and manifest['flash_mb']==4
    for name,digest in manifest['sha256'].items():
        assert hashlib.sha256(directory.joinpath(name).read_bytes()).hexdigest()==digest
