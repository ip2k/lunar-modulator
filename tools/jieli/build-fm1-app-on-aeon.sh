#!/bin/sh
# Build the FM-1 application image (tools/jieli/prepare-fm1-app.py) in the
# lunar-jieli-check container on a LAN node, then measure it. Run ON the node, from a lane
# directory R that holds src/ (git archive of the tree), private/sdk (the pinned AC79
# V1.2.13 SDK checkout) and private/pipeline-system.a (the reviewed scheduler archive).
# Nothing here touches a device; the image is never shared while FM1_GPL_MODS=1.
#   usage: TOOLCHAIN=<JieLi toolchain dir> build-fm1-app-on-aeon.sh R NAME SESSION GPL [preparer args...]
# After the build: flat app.bin from the linked ELF, audit_link and fm1_budget (V15 slot).
set -eu
R=$1; name=$2; session=$3; gpl=$4; shift 4
: "${TOOLCHAIN:?set TOOLCHAIN to the JieLi toolchain directory}"
out=$R/build-$name
test ! -e "$out"
python3 $R/src/tools/jieli/prepare-fm1-app.py --sdk $R/private/sdk --source $R/src --out "$out" \
  --pipeline-system-archive $R/private/pipeline-system.a --gpl "$gpl" "$@" > $R/prep-$name.log 2>&1
docker run --rm --network none --cgroup-parent=docker-batch.slice --cpus=4 --memory=4g --memory-swap=4g \
  --label project=lunar-modulator --label session=$session --user "$(id -u):$(id -g)" \
  -v $TOOLCHAIN:/opt/jieli:ro -v $R:$R -w "$out/apps/demo/demo_hello/board/wl82" \
  lunar-jieli-check:bookworm make -j4 > $R/build-$name.log 2>&1
ELF=$out/cpu/wl82/tools/sdk.elf
python3 - "$R" "$name" <<'PY'
import sys
from pathlib import Path
root, name = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(root/'src/tools/jieli'))
from audit_link import Elf
e = Elf((root/('build-'+name)/'cpu/wl82/tools/sdk.elf').read_bytes())
flat = bytearray()
for n, l in [('text', 0x02000120), ('data', 'data_lma'), ('dynamic_data', 'dynamic_data_lma'),
             ('ram0_data', '_ram0_data_lma'), ('cache_ram_data', 'cache_ram_data_lma')]:
    if isinstance(l, str): l = e.symbol_value(l)
    sec = next(s for s in e.sections if s['name'] == '.' + n)
    assert l - 0x02000120 == len(flat), n
    flat.extend(e.data[sec['offset']:sec['offset'] + sec['size']])
(root/('app-'+name+'.bin')).write_bytes(flat); print('app.bin', len(flat))
PY
set +e
python3 $R/src/tools/jieli/audit_link.py --elf $ELF --app $R/app-$name.bin --json $R/audit-$name.json \
  > $R/audit-$name.log 2>&1; echo "audit exit $?"
python3 $R/src/tools/jieli/fm1_budget.py $R/app-$name.bin --elf $ELF > $R/budget-$name.log 2>&1
echo "budget exit $?"
python3 $R/src/tools/jieli/fm1_budget.py $R/app-$name.bin --elf $ELF --json > $R/budget-$name.json 2>&1
echo BUILDDONE
