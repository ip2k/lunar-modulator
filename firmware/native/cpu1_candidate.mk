# SPDX-License-Identifier: MIT. Separate OFFLINE artifact; no installer target.
# make -f firmware/native/cpu1_candidate.mk ROOT=. TOOLCHAIN=... BUILD=... \
#      OFFLINE_CANDIDATE=1 STOCK_SPL=1
ifneq ($(OFFLINE_CANDIDATE),1)
$(error Explicit OFFLINE_CANDIDATE=1 required; this is not execution admission)
endif
ifneq ($(STOCK_SPL),1)
$(error Only explicit STOCK_SPL=1 route is defined)
endif
ifndef TOOLCHAIN
$(error Set the existing pinned TOOLCHAIN directory)
endif
ifndef BUILD
$(error Set an owned BUILD directory with a cleanup lifecycle)
endif
ROOT := $(abspath $(ROOT))
NATIVE := $(ROOT)/firmware/native
BUILD := $(abspath $(BUILD))
CPU1_CC := $(TOOLCHAIN)/common/bin/clang
CPU1_LD := $(TOOLCHAIN)/pi32v2/bin/ld
CPU1_FLAGS := -target pi32v2 -mcpu=r3 -mfprev1 -std=c11 -Os -ffreestanding -fno-builtin -ffunction-sections -fdata-sections -Wall -Wextra -Werror -Wno-unused-function -I$(NATIVE) -I$(TOOLCHAIN)/pi32v2/include -DLUNAR_NATIVE_PIPELINE_OFFLINE_CANDIDATE=1 -DLUNAR_CPU1_CANDIDATE_STOCK_SPL=1 -DLUNAR_CPU1_CANDIDATE_PI32V2=1
CPU1_NAMES := cpu1_candidate cpu1_candidate_target cpu1_candidate_profile renderer_pipeline_native cpu1_candidate_entry
CPU1_OBJECTS := $(addprefix $(BUILD)/,$(addsuffix .o,$(CPU1_NAMES)))
.PHONY: all
all: $(BUILD)/cpu1-offline-candidate.elf
$(BUILD)/%.o: $(NATIVE)/%.c $(wildcard $(NATIVE)/cpu1_candidate*.h) $(NATIVE)/renderer_pipeline_native.h $(ROOT)/firmware/common/renderer_pipeline_core.c $(ROOT)/firmware/common/renderer_pipeline_core.h $(ROOT)/firmware/common/renderer_pipeline_port.h
	@mkdir -p $(BUILD)
	$(CPU1_CC) $(CPU1_FLAGS) -c $< -o $@
$(BUILD)/cpu1_candidate_entry.o: $(NATIVE)/cpu1_candidate_entry.S
	@mkdir -p $(BUILD)
	$(CPU1_CC) $(filter-out -std=c11,$(CPU1_FLAGS)) -c $< -o $@
$(BUILD)/cpu1-offline-candidate.elf: $(CPU1_OBJECTS) $(NATIVE)/cpu1_candidate.ld
	$(CPU1_LD) -T $(NATIVE)/cpu1_candidate.ld --gc-sections -Map=$(BUILD)/cpu1-offline-candidate.map -o $@ $(CPU1_OBJECTS)
