#!/usr/bin/env bash
# tools/jieli/in-container.sh -- the compile check itself, run inside the
# lunar-jieli-check image by tools/jieli/compile-check.sh. Expects:
#
#   /src         engines/, sim/web/ (sources and mk/), firmware/ and tools/jieli/
#                of the tree
#   /opt/jieli   JieLi's Linux toolchain (the archive's top directory), read-only
#   /sdk         the AC79 SDK V1.2.13 checkout (headers + the libraries
#                demo_hello links), read-only. Its libc++ ships math.h.
#   /out         results: per-profile objects and logs, sizes, report.json/.md,
#                and audit_link.json (tools/jieli/audit_link.py over the objects)
#
# Profiles (one full compile each, every object independently, so one
# failure does not hide the others):
#   ladder  -O2 -ffp-contract=off   docs/14's "ladder" profile
#   fast    -O2 -ffp-contract=fast  compared with ladder to find fused ops
#   sdk     -Oz                     the SDK Makefile's own optimisation level
#   pic     -O2 -ffp-contract=off -fPIC   docs/11 §8 unknown 5
# All take the target flags of the SDK's apps/demo/demo_hello/board/wl82/
# Makefile at AC79NN_SDK_V1.2.13 except -flto (bitcode objects have no machine
# code to measure), -g and -w. The SDK generates code at link time (LTO), with
# options on its link line; the code-generation ones are passed here at
# compile time instead (SDK_CODEGEN). Its link-time -inline-threshold=5, a
# size setting, is left out. MIT licence.
set -euo pipefail

SRC=/src
OUT=/out
J=$(nproc 2>/dev/null || echo 4)
TC=/opt/jieli
# V1.2.13's CFLAGS carry -mfprev1 (the FPU revision) and -femulated-tls as
# plain driver flags; both are in JCC so every profile gets them.
JCC="$TC/common/bin/clang -target pi32v2 -mcpu=r3 -mfprev1 -femulated-tls"

# The SDK Makefile's CFLAGS (less -flto, -g, -w, -Oz, and the flags now in JCC).
SDK_FLAGS="-integrated-as -fno-common -fallow-pointer-null -fprefer-gnu-section \
 -Wno-shift-negative-value -Wno-invalid-noreturn -Wframe-larger-than=2560 \
 -mllvm -pi32v2-large-program=true \
 -fms-extensions -fno-unwind-tables -ffunction-sections -fdata-sections -fmessage-length=0 \
 -D_XOPEN_SOURCE=700 -D_GNU_SOURCE -D__ELF__ -D__GCC_PI32V2__ -DSUPPORT_MS_EXTENSIONS"
# From the same Makefile's LFLAGS (--plugin-opt=...): SIMD, rep memops,
# it-blocks off and the global-merge window. The FPU revision is now -mfprev1.
SDK_CODEGEN="-mllvm -pi32v2-enable-simd=true \
 -mllvm -pi32v2-enable-rep-memop -mllvm -pi32v2-always-use-itblock=false \
 -mllvm -pi32v2-merge-max-offset=4096"
# V1.2.13 include set: the SDK's demo_hello INCLUDES (the C++, driver and
# system headers a firmware build sees), in the SDK's order. V1.2.13's libc++
# (version 12) is configured for pthread and ships its own math.h, so no shim
# is needed; but <memory> and friends pull <__threading_support> ->
# simple_pthread -> FreeRTOS/FreeRTOS.h -> the wl82 port, which needs the
# driver and system headers below. The bt/btstack includes demo_hello also
# lists are left out: our DSP and sim code does not reach them.
SDK_INC="-I/sdk/include_lib/c++ -I/sdk/include_lib/c++/include \
 -I/sdk/include_lib/c++/simple_pthread -I/sdk/include_lib/newlib/include \
 -I/sdk/include_lib -I/sdk/include_lib/driver -I/sdk/include_lib/driver/device \
 -I/sdk/include_lib/driver/cpu/wl82 -I/sdk/include_lib/system \
 -I/sdk/include_lib/system/generic -I/sdk/include_lib/system/os \
 -I/sdk/include_lib/update -I/sdk/include_lib/utils \
 -I/sdk/include_lib/utils/syscfg -I/sdk/include_lib/utils/event \
 -I/sdk/include_lib/media -I$TC/pi32v2/include"

PROFILES=(
  "ladder|-O2|-ffp-contract=off"
  "fast|-O2|-ffp-contract=fast"
  "sdk|-Oz|"
  "pic|-O2|-ffp-contract=off -fPIC"
)

mkdir -p "$OUT"
cd "$SRC/engines"

mk() {  # mk BUILD OPT EXTRA TARGET...
  local build=$1 opt=$2 extra=$3; shift 3
  make -s -C "$SRC/engines" -f Makefile -f "$SRC/sim/web/mk/sim.mk" -f "$SRC/tools/jieli/objects.mk" \
    SIM="$SRC/sim/web" BUILD="$build" CC="$JCC" CXX="$JCC" OPT="$opt" EXTRA="$extra" "$@"
}

build_one() {  # build_one PROFILE BUILD OPT EXTRA OBJ
  local profile=$1 build=$2 opt=$3 extra=$4 obj=$5
  local rel=${obj#"$build"/}
  local log="$OUT/$profile/logs/$rel.log"
  mkdir -p "$(dirname "$log")"
  set +e
  mk "$build" "$opt" "$extra" "$obj" >"$log" 2>&1
  echo $? >"$log.rc"
  set -e
}
export -f mk build_one
export SRC OUT JCC

echo "== toolchain: $($TC/common/bin/clang --version | head -1)"
FAIL_COMPILE=0
echo "== GPL switch: FM1_GPL_MODS=${FM1_GPL_MODS:-1} (engines/Makefile)"
echo "== module list: FM1_MODULES=${FM1_MODULES:-all} (engines/modules/catalogue.mk)"
for p in "${PROFILES[@]}"; do
  IFS='|' read -r name opt add <<<"$p"
  build=$OUT/$name/obj
  extra="$SDK_FLAGS $SDK_CODEGEN $add $SDK_INC"
  rm -rf "$OUT/$name" && mkdir -p "$build"
  printf '%s\n' "$opt $add" >"$OUT/$name/opt.txt"
  printf '%s\n' "$extra" >"$OUT/$name/extra.txt"
  mk "$build" "$opt" "$extra" print-objs >"$OUT/$name/objects.txt"
  mk "$build" "$opt" "$extra" print-modules >"$OUT/$name/modules.txt"
  n=$(wc -l <"$OUT/$name/objects.txt")
  echo "== profile $name ($opt $add): $n objects"
  # One make per object, in parallel: a failing compile is recorded, not fatal.
  xargs -P "$J" -I{} bash -c 'build_one "$@"' _ "$name" "$build" "$opt" "$extra" {} \
    <"$OUT/$name/objects.txt"
  fails=$(grep -L '^0$' $(find "$OUT/$name/logs" -name '*.rc') | wc -l)
  echo "   failed: $fails"
  if [ "$fails" -ne 0 ]; then FAIL_COMPILE=1; fi
done

echo "== disassembly (ladder), for stack frames"
# objsizedump -dump-stack-size prints 0 for every function of an unlinked
# object, so analyze.py reads each prologue's register push and sp adjustment.
mkdir -p "$OUT/ladder/disasm"
while read -r obj; do
  [ -f "$obj" ] || continue
  rel=${obj#"$OUT/ladder/obj/"}
  mkdir -p "$(dirname "$OUT/ladder/disasm/$rel")"
  "$TC/pi32v2/bin/objdump" -d -mcpu=r3 -mattr=+fprev1 "$obj" >"$OUT/ladder/disasm/$rel.txt" 2>&1 || true
done <"$OUT/ladder/objects.txt"

echo "== instance and struct sizes: pi32v2, i386, x86-64"
SZ=$OUT/sizes
rm -rf "$SZ" && mkdir -p "$SZ"
SZ_CXX="-std=c++11 -fno-exceptions -fno-rtti -DTEST -O2 -Iinclude -isystem third_party/mutable -isystem third_party/schwung -isystem third_party/msfa"
SZ_C="-std=c99 -O2 -Iinclude -Iseq -Imod -I$SRC/sim/web/src"
sz_compile() {  # sz_compile TARGET-NAME "CC" "EXTRA"
  local t=$1 cc=$2 extra=$3
  mkdir -p "$SZ/$t"
  for e in MACRO SHAPES MACRO_HEAVY SIXOP DX7 TEST_SINE TEST_GAIN MI_FX SCHWUNG; do
    $cc $SZ_CXX $extra -DSZ_$e -c "$SRC/tools/jieli/sizes.cc" -o "$SZ/$t/sizes_$e.o" \
      >"$SZ/$t/sizes_$e.log" 2>&1 || echo "   $t SZ_$e failed (see $SZ/$t/sizes_$e.log)"
  done
  if [ "${FM1_GPL_MODS:-1}" != 0 ]; then     # the GPL modules, while the switch is on
    for e in ACID_BASS COMET_KIT CRATER; do
      $cc $SZ_CXX $extra -I"$SRC/engines/third_party/fm1-x0x" -I"$SRC/engines/third_party/fm1-x0x/gen" \
        -I"$OUT/ladder/obj/gen" -DSZ_$e -c "$SRC/tools/jieli/sizes.cc" -o "$SZ/$t/sizes_$e.o" \
        >"$SZ/$t/sizes_$e.log" 2>&1 || echo "   $t SZ_$e failed (see $SZ/$t/sizes_$e.log)"
    done
  fi
  $cc $SZ_C $extra -c "$SRC/tools/jieli/sizes.c" -o "$SZ/$t/sizes_c.o" \
    >"$SZ/$t/sizes_c.log" 2>&1 || echo "   $t sizes.c failed (see $SZ/$t/sizes_c.log)"
  if [ "${FM1_GPL_MODS:-1}" != 0 ]; then     # Felucca's engines (GPL), while the switch is on
    $cc $SZ_CXX $extra -I"$OUT/ladder/obj/gen" -DSZ_FELUCCA -c "$SRC/tools/jieli/sizes.cc" \
      -o "$SZ/$t/sizes_FELUCCA.o" >"$SZ/$t/sizes_FELUCCA.log" 2>&1 \
      || echo "   $t SZ_FELUCCA failed (see $SZ/$t/sizes_FELUCCA.log)"
    $cc -std=gnu11 -fwrapv -O2 -w $extra -Iinclude -I"$OUT/ladder/obj/gen" -Isrc -Ithird_party/felucca/src \
      -Ithird_party/felucca/gen -c "$SRC/tools/jieli/sizes_felucca.c" -o "$SZ/$t/sizes_felucca_c.o" \
      >"$SZ/$t/sizes_felucca_c.log" 2>&1 || echo "   $t sizes_felucca.c failed (see $SZ/$t/sizes_felucca_c.log)"
  fi
}
sz_compile pi32v2 "$JCC" "$SDK_FLAGS $SDK_CODEGEN $SDK_INC"
sz_compile i386 "gcc -m32" "-w"
sz_compile x86_64 "gcc -m64" "-w"

echo "== fm1_seq_size() at the FM-1 defaults, run on i386 and x86-64"
for t in i386:-m32 x86_64:-m64; do
  name=${t%%:*}; flag=${t#*:}
  make -s -C "$SRC/engines" BUILD="$OUT/host-$name" CC="gcc $flag" CXX="g++ $flag" -j"$J" \
    "$OUT/host-$name/fm1-seq" >"$SZ/fm1-seq-$name.log" 2>&1 \
    && "$OUT/host-$name/fm1-seq" --sizes >"$SZ/seq-sizes-$name.json" 2>>"$SZ/fm1-seq-$name.log" \
    || echo "   fm1-seq $name failed (see $SZ/fm1-seq-$name.log)"
done

echo "== library symbols: what demo_hello links (V1.2.13 newlib, libc++ and closed libraries)"
# The SDK's own libraries are LLVM bitcode; nm reads them through the gold
# plugin. V1.2.13 links newlib and libc++ from the SDK tree, not lib/r3.
LS=$OUT/libsyms
rm -rf "$LS" && mkdir -p "$LS"
for a in /sdk/include_lib/newlib/pi32v2-lib/libc.a /sdk/include_lib/newlib/pi32v2-lib/libm.a \
         /sdk/include_lib/newlib/pi32v2-lib/libcompiler_rt.a \
         /sdk/include_lib/c++/libstdc++/libc++.a /sdk/include_lib/c++/libstdc++/libc++abi.a \
         /sdk/include_lib/c++/libstdc++/libemutls.a \
         /sdk/cpu/wl82/liba/{cpu,event,system,cfg_tool,fs,common_lib,update}.a; do
  [ -f "$a" ] || { echo "   missing $a"; continue; }
  "$TC/pi32v2/bin/nm" --plugin "$TC/common/bin/LLVMgold.so" -g --defined-only "$a" 2>/dev/null \
    | awk 'NF==3 {print $3}' | sort -u >"$LS/$(basename "$a" .a).txt" || true
done

echo "== analysis"
python3 "$SRC/tools/jieli/analyze.py" "$OUT"

echo "== boot_info bridge on pi32v2 (firmware/third_party/fm1-nes/boot_compat.c)"
# It runs before RAM is initialised, so its object may call nothing but the
# SDK's boot_info_init (no memcpy/memset the volatile copy should prevent).
# Test mode (-DFM1_BOOT_COMPAT_TEST) skips the SDK app_config.h, which only a
# real app has; the code is the same. Ladder and SDK optimisation levels.
BB=$OUT/boot-bridge
rm -rf "$BB" && mkdir -p "$BB"
for o in O2 Oz; do
  $JCC $SDK_FLAGS $SDK_CODEGEN $SDK_INC -$o -DFM1_BOOT_COMPAT_TEST -c \
    "$SRC/firmware/third_party/fm1-nes/boot_compat.c" -o "$BB/boot_compat-$o.o" >"$BB/boot_compat-$o.log" 2>&1 \
    || { echo "   boot bridge -$o failed to compile (see $BB/boot_compat-$o.log)"; FAIL_AUDIT=1; continue; }
  "$TC/pi32v2/bin/objdump" -d -mcpu=r3 -mattr=+fprev1 "$BB/boot_compat-$o.o" >"$BB/boot_compat-$o.dis.log" 2>&1 || true
  und=$("$TC/pi32v2/bin/nm" -u "$BB/boot_compat-$o.o" | awk '{print $NF}' | sort -u | tr '\n' ' ')
  echo "$und" >"$BB/boot_compat-$o.undefined.log"
  if [ "$und" = "__real_boot_info_init " ]; then
    echo "   -$o: calls only __real_boot_info_init"
  else
    echo "   -$o: unexpected undefined symbols: $und"; FAIL_AUDIT=1
  fi
done

echo "== link-audit (compile-only: over the ladder objects and the boot bridge)"
# The compile-time half of the key-check safeguards (see audit_link.py): no
# forbidden key-check symbol or reference, no eFuse-controller access, no SDK
# key-blob bytes, no use of the 0x0200012E stub, the key-check mailbox or the
# IRQ-123 vector in our own objects, and no request_irq(123) in our sources.
# The link-time checks (the late_initcall group, attribution of SDK hits,
# sdk_meky_check's exact scheduling) run on the real link later.
python3 "$SRC/tools/jieli/audit_link.py" --objects "$OUT/ladder/obj" --objects "$BB" \
  --sources "$SRC/engines" --sources "$SRC/sim/web/src" --sources "$SRC/firmware" \
  --json "$OUT/audit_link.json" || { echo "   LINK AUDIT FAILED (see $OUT/audit_link.json)"; FAIL_AUDIT=1; }
[ -z "${FAIL_AUDIT:-}" ] && [ "$FAIL_COMPILE" -eq 0 ] || exit 1
