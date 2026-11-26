# Headless simulator for the shared UI code (firmware/src/ui + portable services).
# LVGL and ArduinoJson come from the PlatformIO libdeps so both targets use the
# exact same library versions. Run `pio pkg install` in firmware/ first.
ROOT    := $(abspath ..)
FW      := $(ROOT)/firmware
LIBDEPS := $(FW)/.pio/libdeps/ili9341
LVGL    := $(LIBDEPS)/lvgl
AJSON   := $(LIBDEPS)/ArduinoJson/src
BUILD   := build

CFLAGS_COMMON := -O2 -g -DSIMULATOR=1 -DLV_CONF_INCLUDE_SIMPLE -DLV_LVGL_H_INCLUDE_SIMPLE \
                 -I$(FW)/include -I$(FW)/src -I$(LVGL) -I$(LVGL)/src -I$(AJSON)
CFLAGS   := $(CFLAGS_COMMON) -w
CXXFLAGS := $(CFLAGS_COMMON) -std=c++17 -Wall -Wno-unused-function -Wno-missing-field-initializers

LVGL_SRC := $(shell find $(LVGL)/src -name '*.c')
LVGL_OBJ := $(patsubst $(LVGL)/src/%.c,$(BUILD)/lvgl/%.o,$(LVGL_SRC))

APP_SRC := $(wildcard $(FW)/src/ui/*.cpp) $(FW)/src/services/pack.cpp $(FW)/src/services/clock.cpp \
           $(FW)/src/services/timeline.cpp $(FW)/src/hal/audio.cpp sim_main.cpp
APP_OBJ := $(patsubst %.cpp,$(BUILD)/app/%.o,$(notdir $(APP_SRC)))

vpath %.cpp $(FW)/src/ui $(FW)/src/services $(FW)/src/hal .

all: $(BUILD)/sim

$(BUILD)/liblvgl.a: $(LVGL_OBJ)
	@ar rcs $@ $^

$(BUILD)/lvgl/%.o: $(LVGL)/src/%.c $(FW)/include/lv_conf.h
	@mkdir -p $(dir $@)
	@cc $(CFLAGS) -c $< -o $@

$(BUILD)/app/%.o: %.cpp $(wildcard $(FW)/src/ui/*.h $(FW)/src/services/*.h $(FW)/src/hal/*.h) $(FW)/include/lv_conf.h
	@mkdir -p $(dir $@)
	c++ $(CXXFLAGS) -c $< -o $@

$(BUILD)/sim: $(APP_OBJ) $(BUILD)/liblvgl.a
	c++ $^ -lz -o $@

clean:
	rm -rf $(BUILD)

.PHONY: all clean
