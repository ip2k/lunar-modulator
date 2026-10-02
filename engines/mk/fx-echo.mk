# mk/fx-echo.mk -- Echo, the ping-pong delay written here
# (engines/src/fx_echo.cc), and its selftest.
#
# This fragment adds a target to `all` before the main Makefile's first rule;
# keep `all` the default goal.
.DEFAULT_GOAL := all

OUR_SRC += src/fx_echo.cc

# fm1-echo-selftest: what a render cannot show -- parameters turned while it
# runs, host rates it must refuse, decay to exact zeros (run by
# tests/test_engines_echo.py). Not in OUR_SRC: it has a main().
ECHO_SELFTEST_OBJ := $(BUILD)/our/test/echo_selftest.o $(BUILD)/our/src/fx_echo.o

all: $(BUILD)/fm1-echo-selftest

$(BUILD)/fm1-echo-selftest: $(ECHO_SELFTEST_OBJ)
	$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm
