# MIT. Read after engines/Makefile. Application HAL and host renderer excluded.
# This lists the real engine product objects, including selected GPL modules.
NATIVE_ENGINE_OBJ := $(sort $(filter-out $(BUILD)/our/host/render.o,$(RENDER_PRODUCT_OBJ)))
.PHONY: print-native-engine-objs
print-native-engine-objs:
	@printf '%s\n' $(NATIVE_ENGINE_OBJ)
