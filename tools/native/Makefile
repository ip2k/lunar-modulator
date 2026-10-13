# MIT. SDK-free arithmetic support for the pi32v2 native application.
ROOT := $(abspath ../..)
RUNTIME := $(ROOT)/firmware/third_party/compiler-rt
BUILD ?= $(ROOT)/build/native-arithmetic
JIELI_TOOLCHAIN ?=
CC := $(JIELI_TOOLCHAIN)/pi32v2/bin/clang
LD := $(JIELI_TOOLCHAIN)/pi32v2/bin/ld
OBJDUMP := $(JIELI_TOOLCHAIN)/common/bin/objdump
SOURCES := adddf3 addsf3 comparedf2 comparesf2 divdf3 divdi3 divsf3 extendsfdf2 \
           fixsfsi floatsisf fp_mode muldf3 mulsf3 subdf3 subsf3 truncdfsf2 udivmoddi4 \
           fixdfdi fixdfsi fixunsdfsi fixunssfdi floatdisf floatsidf floatundisf \
           floatunsidf moddi3 udivdi3 umoddi3 fixunsdfdi floatdidf floatundidf
OBJECTS := $(addprefix $(BUILD)/,$(addsuffix .o,$(SOURCES)))
HEADERS := $(wildcard $(RUNTIME)/*.h $(RUNTIME)/*.inc)
FLAGS := -target pi32v2 -Os -ffreestanding -fno-builtin -ffunction-sections

.PHONY: all check-pins
all: check-pins $(BUILD)/arithmetic-linked.o
	$(OBJDUMP) -t $(BUILD)/arithmetic-linked.o > $(BUILD)/symbols.txt
	python3 -c 'import pathlib,re; s=pathlib.Path("$(BUILD)/symbols.txt").read_text(); missing=re.findall(r"^.*\*UND\*[ \t]+00000000[ \t]+(\S+)[ \t]*$$",s,re.M); assert not missing, missing'

check-pins:
	python3 -c 'import hashlib,json,pathlib; p=pathlib.Path("$(RUNTIME)"); m=json.loads((p/"inventory.json").read_text()); bad=[n for n,h in m["files"].items() if hashlib.sha256((p/n).read_bytes()).hexdigest()!=h]; assert not bad,bad'

$(BUILD):
	mkdir -p $@

$(BUILD)/%.o: $(RUNTIME)/%.c $(HEADERS) | $(BUILD)
	$(CC) $(FLAGS) -c $< -o $@

$(BUILD)/arithmetic-probe.o: arithmetic_probe.c | $(BUILD)
	$(CC) $(FLAGS) -c $< -o $@

$(BUILD)/arithmetic-linked.o: $(OBJECTS) $(BUILD)/arithmetic-probe.o
	$(LD) -r $^ -o $@
