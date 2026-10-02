#!/usr/bin/env bash
# tools/jieli/in-container.sh -- the compile check itself, run inside the
# lunar-jieli-check image by tools/jieli/compile-check.sh. Expects:
#
#   /src         engines/, sim/web/ (sources and mk/) and tools/jieli/ of the tree
#   /opt/jieli   JieLi's Linux toolchain (the archive's top directory), read-only
#   /sdk         the AC79 SDK checkout (include_lib/c++ only is needed), read-only
#   /cxxshim     libc++ 7.0.0's math.h (see compile-check.sh), read-only
#   /out         results: per-profile objects and logs, sizes, report.json/.md
#
# Profiles (one full compile each, every object independently, so one
# failure does not hide the others):
#   ladder  -O2 -ffp-contract=off   docs/14's "ladder" profile
#   fast    -O2 -ffp-contract=fast  compared with ladder to find fused ops
#   sdk     -Oz                     the SDK Makefile's own optimisation level
#   pic     -O2 -ffp-contract=off -fPIC   docs/11 §8 unknown 5
# All take the target flags of the SDK's apps/demo/demo_hello/board/wl82/
# Makefile at AC79NN_SDK_V1.1.9 except -flto (bitcode objects have no machine
# code to measure), -g and -w. The SDK generates code at link time (LTO), with
# options on its link line; the code-generation ones are passed here at
# compile time instead (SDK_CODEGEN). Its link-time -inline-threshold=5, a
# size setting, is left out. MIT licence.
set -euo pipefail

SRC=/src
OUT=/out
J=$(nproc 2>/dev/null || echo 4)
TC=/opt/jieli
JCC="$TC/common/bin/clang -target pi32v2 -mcpu=r3"

# The SDK Makefile's CFLAGS (less -flto, -g, -w, -Oz) and the defines and
# include order its C++ code relies on: libc++ headers, then the C library.
SDK_FLAGS="-integrated-as -fno-common -fallow-pointer-null -fprefer-gnu-section \
 -Wno-shift-negative-value -Wframe-larger-than=2560 -mllvm -pi32v2-large-program=true \
 -fms-extensions -fno-unwind-tables -ffunction-sections -fdata-sections -fmessage-length=0 \
 -D_XOPEN_SOURCE=700 -D_GNU_SOURCE -D_LIBCPP_HAS_NO_THREADS -D_LIBCPP_NO_EXCEPTIONS \
 -D_LIBCPP_HAS_NO_ALIGNED_ALLOCATION -D__ELF__ -D__GCC_PI32V2__ -DSUPPORT_MS_EXTENSIONS"
# From the same Makefile's LFLAGS (--plugin-opt=...): the FPU revision, SIMD,
# rep memops, it-blocks off and the global-merge window.
SDK_CODEGEN="-Xclang -target-feature -Xclang +fprev1 -mllvm -pi32v2-enable-simd=true \
 -mllvm -pi32v2-enable-rep-memop -mllvm -pi32v2-always-use-itblock=false \
 -mllvm -pi32v2-merge-max-offset=4096"
SDK_INC="-I/sdk/include_lib/c++/include -I/cxxshim -I$TC/pi32v2/include"

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
for p in "${PROFILES[@]}"; do
  IFS='|' read -r name opt add <<<"$p"
  build=$OUT/$name/obj
  extra="$SDK_FLAGS $SDK_CODEGEN $add $SDK_INC"
  rm -rf "$OUT/$name" && mkdir -p "$build"
  printf '%s\n' "$opt $add" >"$OUT/$name/opt.txt"
  printf '%s\n' "$extra" >"$OUT/$name/extra.txt"
  mk "$build" "$opt" "$extra" print-objs >"$OUT/$name/objects.txt"
  n=$(wc -l <"$OUT/$name/objects.txt")
  echo "== profile $name ($opt $add): $n objects"
  # One make per object, in parallel: a failing compile is recorded, not fatal.
  xargs -P "$J" -I{} bash -c 'build_one "$@"' _ "$name" "$build" "$opt" "$extra" {} \
    <"$OUT/$name/objects.txt"
  fails=$(grep -L '^0$' $(find "$OUT/$name/logs" -name '*.rc') | wc -l)
  echo "   failed: $fails"
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
SZ_CXX="-std=c++11 -fno-exceptions -fno-rtti -DTEST -O2 -Iinclude -isystem third_party/mutable -isystem third_party/schwung"
SZ_C="-std=c99 -O2 -Iinclude -Iseq -I$SRC/sim/web/src"
sz_compile() {  # sz_compile TARGET-NAME "CC" "EXTRA"
  local t=$1 cc=$2 extra=$3
  mkdir -p "$SZ/$t"
  for e in MACRO SHAPES MACRO_HEAVY SIXOP TEST_SINE TEST_GAIN MI_FX SCHWUNG; do
    $cc $SZ_CXX $extra -DSZ_$e -c "$SRC/tools/jieli/sizes.cc" -o "$SZ/$t/sizes_$e.o" \
      >"$SZ/$t/sizes_$e.log" 2>&1 || echo "   $t SZ_$e failed (see $SZ/$t/sizes_$e.log)"
  done
  $cc $SZ_C $extra -c "$SRC/tools/jieli/sizes.c" -o "$SZ/$t/sizes_c.o" \
    >"$SZ/$t/sizes_c.log" 2>&1 || echo "   $t sizes.c failed (see $SZ/$t/sizes_c.log)"
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

echo "== library symbols: what demo_hello links (lib/r3, the SDK's libc++ and libraries)"
# The SDK's own libraries are LLVM bitcode; nm reads them through the gold plugin.
LS=$OUT/libsyms
rm -rf "$LS" && mkdir -p "$LS"
for a in "$TC/pi32v2/lib/r3/libc.a" "$TC/pi32v2/lib/r3/libm.a" "$TC/pi32v2/lib/r3/libcompiler-rt.a" \
         /sdk/include_lib/c++/libstdc++/libcxx.a /sdk/include_lib/c++/libstdc++/libcxxabi.a \
         /sdk/cpu/wl82/liba/{cpu,event,system,cfg_tool,fs,common_lib,update}.a; do
  [ -f "$a" ] || { echo "   missing $a"; continue; }
  "$TC/pi32v2/bin/nm" --plugin "$TC/common/bin/LLVMgold.so" -g --defined-only "$a" 2>/dev/null \
    | awk 'NF==3 {print $3}' | sort -u >"$LS/$(basename "$a" .a).txt" || true
done

echo "== analysis"
python3 "$SRC/tools/jieli/analyze.py" "$OUT"
