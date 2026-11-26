/* LVGL 9.2 configuration shared by the device firmware and the PC simulator.
 * Anything not set here takes LVGL's default (lv_conf_internal.h). */
#ifndef LV_CONF_H
#define LV_CONF_H

#define LV_COLOR_DEPTH 16

/* Memory: use the system heap (no fixed LVGL pool) so fonts and decoded
 * video frames can use whatever the ESP32 has free. */
#define LV_USE_STDLIB_MALLOC  LV_STDLIB_CLIB
#define LV_USE_STDLIB_STRING  LV_STDLIB_CLIB
#define LV_USE_STDLIB_SPRINTF LV_STDLIB_CLIB

#define LV_DEF_REFR_PERIOD 16
#define LV_DPI_DEF 130

/* Rendering */
#define LV_USE_DRAW_SW 1
#define LV_DRAW_SW_SUPPORT_RGB565   1
#define LV_DRAW_SW_SUPPORT_RGB565A8 1
#define LV_DRAW_SW_SUPPORT_RGB888   1
#define LV_DRAW_SW_SUPPORT_XRGB8888 1
#define LV_DRAW_SW_SUPPORT_ARGB8888 1
#define LV_DRAW_SW_SUPPORT_L8       0
#define LV_DRAW_SW_SUPPORT_AL88     0
#define LV_DRAW_SW_SUPPORT_A8       1
#define LV_DRAW_SW_SUPPORT_I1       0
#define LV_DRAW_SW_COMPLEX 1
/* Simple layers (opacity during fade transitions) render in chunks of this size. */
#define LV_DRAW_LAYER_SIMPLE_BUF_SIZE (16 * 1024)
#define LV_DRAW_SW_DRAW_UNIT_CNT 1

/* No image cache: file images are decoded strip by strip as they are drawn. */
#define LV_CACHE_DEF_SIZE 0
#define LV_IMAGE_HEADER_CACHE_DEF_CNT 16

/* Logging */
#define LV_USE_LOG 1
#define LV_LOG_LEVEL LV_LOG_LEVEL_WARN
#define LV_LOG_PRINTF 1

#define LV_USE_ASSERT_NULL 1
#define LV_USE_ASSERT_MALLOC 1

/* Fonts. Montserrat 14 is only used by the hidden maintenance menu (a logged
 * deviation); pack text always uses the pack's own binary fonts. */
#define LV_FONT_MONTSERRAT_14 1
#define LV_FONT_MONTSERRAT_12 0
#define LV_FONT_MONTSERRAT_16 0
#define LV_FONT_DEFAULT &lv_font_montserrat_14
#define LV_USE_FONT_PLACEHOLDER 0
#define LV_USE_BINFONT 1

/* Text */
#define LV_TXT_ENC LV_TXT_ENC_UTF8
#define LV_USE_BIDI 0
#define LV_USE_ARABIC_PERSIAN_CHARS 0

/* Widgets: only what the renderer and hidden menu use. */
#define LV_WIDGETS_HAS_DEFAULT_VALUE 0
#define LV_USE_ANIMIMG    0
#define LV_USE_ARC        0
#define LV_USE_BAR        0
#define LV_USE_BUTTON     1
#define LV_USE_BUTTONMATRIX 1
#define LV_USE_CALENDAR   0
#define LV_USE_CANVAS     0
#define LV_USE_CHART      0
#define LV_USE_CHECKBOX   0
#define LV_USE_DROPDOWN   0
#define LV_USE_IMAGE      1
#define LV_USE_IMAGEBUTTON 0
#define LV_USE_KEYBOARD   1
#define LV_USE_LABEL      1
#define LV_LABEL_TEXT_SELECTION 0
#define LV_LABEL_LONG_TXT_HINT 1
#define LV_USE_LED        0
#define LV_USE_LINE       0
#define LV_USE_LIST       0
#define LV_USE_LOTTIE     0
#define LV_USE_MENU       0
#define LV_USE_MSGBOX     0
#define LV_USE_ROLLER     0
#define LV_USE_SCALE      0
#define LV_USE_SLIDER     0
#define LV_USE_SPAN       0
#define LV_USE_SPINBOX    0
#define LV_USE_SPINNER    0
#define LV_USE_SWITCH     0
#define LV_USE_TEXTAREA   1
#define LV_USE_TABLE      0
#define LV_USE_TABVIEW    0
#define LV_USE_TILEVIEW   0
#define LV_USE_WIN        0

/* No framework look (PLAN.md §7.1): no default theme. */
#define LV_USE_THEME_DEFAULT 0
#define LV_USE_THEME_SIMPLE  0
#define LV_USE_THEME_MONO    0

#define LV_USE_FLEX 1
#define LV_USE_GRID 0

/* File systems: the SD card is drive 'S' on both targets. */
#if defined(SIMULATOR)
  #define LV_USE_FS_STDIO 1
  #define LV_FS_STDIO_LETTER 'S'
  #define LV_FS_STDIO_PATH ""
  #define LV_FS_STDIO_CACHE_SIZE 4096
#else
  #define LV_USE_FS_ARDUINO_SD 1
  #define LV_FS_ARDUINO_SD_LETTER 'S'
#endif

/* Image decoders */
#define LV_BIN_DECODER_RAM_LOAD 0
#define LV_USE_TJPGD 1   /* used by the MJPEG video player */
#define LV_USE_LODEPNG 0
#define LV_USE_LIBPNG  0
#define LV_USE_BMP     0

#define LV_USE_SNAPSHOT 0
#define LV_USE_SYSMON   0
#define LV_USE_PROFILER 0
#define LV_USE_OBSERVER 1

#define LV_BUILD_EXAMPLES 0
#define LV_USE_DEMO_WIDGETS 0

#endif
