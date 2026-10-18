_expected_source = 'fef11263c88f4b79193ceff9b590094110124491'
_pins = {'tools/cynthion_usb_key/build.py': 'b57ec400cef588a333fc109634ba5d55203bab199d9168e35173a73d930633fa', 'tools/cynthion_usb_key/top.py': '2f0ba70006b5531b890147f84da9bbc7f444cd7bfbe493f5b6151d6218c7f5c6', 'tools/cynthion_usb_key/gateware.py': 'd260878aa2add66ebc5a13cd5b46ee74edb5fe335a2727e3c3109899e3331b86', 'gateware/ulpi_safe_phy.py': '88483a1b828c52ec5e3e64c3600af29a270bc8cd2029364a851087f85eab21f1', 'dongle/sim/params.py': 'f3f8f883cc433e55f704030e0dbde18efc76580a5610d18f176ebb8592c9b93c', 'dongle/firmware/config.h': '82686343ad43505fd58fb7a24c3bdb744521ee6abb046eb47226084ea4ebb0e2'}
import hashlib, importlib.metadata, os, pathlib, runpy, subprocess, sys
assert os.environ['SOURCE_COMMIT'] == _expected_source
assert 'AMARANTH_ENV_TRELLIS' not in os.environ
assert sys.version_info[:3] == (3,12,3), sys.version
os.chdir('/workspace')
for name,digest in _pins.items():
 assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==digest,name
for name,version in {'amaranth':'0.5.10','apollo-fpga':'1.1.1','cynthion':'0.2.5','luna-usb':'0.2.3','luna-soc':'0.3.2'}.items():
 assert importlib.metadata.version(name)==version,name
for name in ('yosys','nextpnr-ecp5','ecppack'):
 subprocess.run(['/opt/oss-cad-suite/bin/'+name,'--version'],check=True)
print('PICO REPEAT BUILD PREFLIGHT PASSED',flush=True)
sys.path.insert(0,'/workspace')
sys.argv=['build','--build-dir','/output/build','--mode','pico-repeat','--target-power-from-control']
runpy.run_module('tools.cynthion_usb_key.build',run_name='__main__')
