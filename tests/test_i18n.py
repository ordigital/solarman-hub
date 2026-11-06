"""Translation catalogs must stay complete and preserve interpolation fields."""
from importlib.resources import files
import json
import re

def test_translation_catalogs_are_complete():
    catalog=json.loads(files('solarman_hub').joinpath('static/locales.json').read_text())
    assert set(catalog)=={'en','pl','de','fr','cs','sk','lt','uk','ru'}
    source=catalog['en']
    assert len(source)>=200
    for language,messages in catalog.items():
        assert set(messages)==set(source),language
        for key,value in messages.items():
            assert isinstance(value,str) and value.strip(),(language,key)
            assert set(re.findall(r'\{\w+\}',key))==set(re.findall(r'\{\w+\}',value)),(language,key)
