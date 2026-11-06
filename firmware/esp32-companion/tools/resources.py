"""Embed the Hub's canonical data-only decoder. No copied field map."""
from pathlib import Path
import json
Import("env")
project = Path(env['PROJECT_DIR'])
source = project.parents[1]/'src/solarman_hub/builtin_profiles/sofar-hyd-g3-2115.json'
text = json.dumps(json.loads(source.read_text()), separators=(',', ':'), ensure_ascii=True)
output = project/'include/builtin_profile.h'
output.write_text('#pragma once\n#include <Arduino.h>\nstatic const char BUILTIN_PROFILE[] PROGMEM = R"PROFILE('+text+')PROFILE";\n')
