"""Create factory/OTA artifacts and their public integrity manifest after pio run."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

project = Path(__file__).resolve().parents[1]
repository = project.parents[1]
build = project/'.pio/build/esp32dev'
output = project/'dist'
output.mkdir(exist_ok=True)
core = Path(os.environ.get('PLATFORMIO_CORE_DIR', str(Path.home()/'.platformio')))
boot_app = core/'packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin'
shutil.copyfile(build/'firmware.bin',output/'firmware.bin')
subprocess.run([sys.executable,'-m','esptool','--chip','esp32','merge-bin','--flash-mode','dio','--flash-freq','40m','--flash-size','4MB','-o',str(output/'factory.bin'),
    '0x1000',str(build/'bootloader.bin'),'0x8000',str(build/'partitions.bin'),'0xe000',str(boot_app),'0x10000',str(build/'firmware.bin')],check=True)
version = re.search(r'VERSION\[\]="([^"]+)"', (project/'src/main.cpp').read_text()).group(1)
checksums = {name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in ('factory.bin','firmware.bin')}
(output/'SHA256SUMS').write_text(''.join(digest+'  '+str((output/name).relative_to(repository))+'\n' for name,digest in checksums.items()))
(output/'manifest.json').write_text(json.dumps({'version':version,'chip':'esp32','flash_mb':4,'application_offset':'0x10000','factory_offset':'0x0','sha256':checksums},indent=2)+'\n')
