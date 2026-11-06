"""Native checks exercise the exact framing/ACK code compiled into ESP32."""
from pathlib import Path
import shutil
import subprocess
import pytest
from solarman_hub.protocol import Frame

@pytest.mark.skipif(not shutil.which('g++'),reason='Requires native C++ compiler')
def test_native_v5_wire_contract(tmp_path):
    root=Path(__file__).resolve().parents[1]
    source=tmp_path/'wire.cpp'
    source.write_text(r'''
#include "v5_protocol.h"
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
int main(int argc,char **argv){
 std::ifstream input(argv[1]);std::string hex;input>>hex;std::vector<uint8_t> bytes;
 for(size_t i=0;i<hex.size();i+=2)bytes.push_back(std::stoi(hex.substr(i,2),nullptr,16));
 V5::Framer stream;int frames=0;
 stream.feed(0xff,[&](const uint8_t*,size_t){return;});
 for(uint8_t byte:bytes)stream.feed(byte,[&](const uint8_t *data,size_t n){if(!V5::valid(data,n))exit(2);frames++;});
 if(frames!=1||stream.used!=0||stream.invalid!=1)return 3;
 for(uint8_t byte:bytes)stream.feed(byte,[&](const uint8_t*,size_t){stream.clear();});
 if(stream.used!=0)return 4;
 uint8_t reply[23];if(V5::ack(bytes.data(),reply,7,1,60)!=0)return 5;
 if(V5::ack(bytes.data(),reply,7,1793952000,60)!=23||!V5::valid(reply,23))return 6;
 static const char digits[]="0123456789abcdef";
 for(uint8_t byte:reply)std::cout<<digits[byte>>4]<<digits[byte&15];
}
''')
    executable=tmp_path/'wire'
    subprocess.run(['g++','-std=c++17','-Wall','-Werror','-I',str(root/'firmware/esp32-companion/include'),str(source),'-o',str(executable)],check=True,capture_output=True)
    output=subprocess.check_output([str(executable),str(root/'tests/fixtures/sofar-report.hex')],text=True)
    reply=Frame.parse(bytes.fromhex(output))
    assert reply.code==0x1210 and reply.serial==1234567890
    assert int.from_bytes(reply.raw[17:21],'little',signed=True)==60
