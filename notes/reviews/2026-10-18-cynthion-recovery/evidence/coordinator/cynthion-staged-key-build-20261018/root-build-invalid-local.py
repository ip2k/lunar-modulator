import hashlib, importlib.metadata, os, pathlib, runpy, subprocess, sys
assert os.environ['SOURCE_'1998c49055da5f8a130dcac81752f65eb6072604''] == '1998c49055da5f8a130dcac81752f65eb6072604'
assert 'AMARANTH_ENV_TRELLIS' not in os.environ
assert sys.version_info[:3] == (3,12,3), sys.version
os.chdir('/workspace')
for name,digest in {'tools/cynthion_usb_key/build.py': 'f75f5f0f084e48604cddbe072375ce73ece965296d917f840e73ede6abab98d2', 'tools/cynthion_usb_key/top.py': '0519ef72bdb621b7ccc2014928065ce55bbd633b72d5bb366a19d98688e2bdc5', 'tools/cynthion_usb_key/gateware.py': 'bdf35f75758f9278a80eacb5b9f375a567c7ea6b30f8873262e3753d8d46da4a', 'gateware/ulpi_safe_phy.py': '88483a1b828c52ec5e3e64c3600af29a270bc8cd2029364a851087f85eab21f1', 'dongle/sim/params.py': 'f3f8f883cc433e55f704030e0dbde18efc76580a5610d18f176ebb8592c9b93c', 'dongle/firmware/config.h': '82686343ad43505fd58fb7a24c3bdb744521ee6abb046eb47226084ea4ebb0e2'}.items():
 assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==digest,name
for name,version in {'amaranth':'0.5.10','apollo-fpga':'1.1.1','cynthion':'0.2.5','luna-usb':'0.2.3','luna-soc':'0.3.2'}.items():
 assert importlib.metadata.version(name)==version,name
for name in ('yosys','nextpnr-ecp5','ecppack'):
 subprocess.run(['/opt/oss-cad-suite/bin/'+name,'--version'],check=True)
print('STAGED KEY BUILD PREFLIGHT PASSED',flush=True)
sys.path.insert(0,'/workspace')
sys.argv=['build','--build-dir','/output/build','--mode','staged-operation','--target-power-from-control']
runpy.run_module('tools.cynthion_usb_key.build',run_name='__main__')
