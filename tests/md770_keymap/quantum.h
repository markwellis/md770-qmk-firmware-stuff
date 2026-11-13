#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "quantum/keycodes.h"

#define MATRIX_ROWS 16
#define MATRIX_COLS 8
#define RGB_MATRIX_LED_COUNT 85
#define RGB_MATRIX_MAXIMUM_BRIGHTNESS 255
#define RGB_MATRIX_SOLID_COLOR 1
#define RGB_MATRIX_CUSTOM_MD770_CUSTOM 11
#define MO(layer) (QK_MOMENTARY | (layer))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define HSV_WHITE 0, 0, 255
#define HSV_RED 0, 255, 255
#define HSV_ORANGE 21, 255, 255
#define HSV_YELLOW 43, 255, 255
#define HSV_GREEN 85, 255, 255
#define HSV_CYAN 128, 255, 255
#define HSV_BLUE 170, 255, 255
#define HSV_PURPLE 191, 255, 255

typedef uint8_t  matrix_row_t;
typedef uint32_t layer_state_t;
typedef struct {
    uint8_t h, s, v;
} hsv_t;
typedef struct {
    uint8_t r, g, b;
} rgb_t;
typedef struct {
    struct {
        struct {
            uint8_t col, row;
        } key;
        bool pressed;
    } event;
} keyrecord_t;
typedef struct {
    uint8_t matrix_co[MATRIX_ROWS][MATRIX_COLS];
} led_config_t;
extern layer_state_t default_layer_state, layer_state;
extern led_config_t  g_led_config;
uint8_t              get_highest_layer(layer_state_t state);
void                 default_layer_set(layer_state_t state);
bool                 layer_state_is(uint8_t layer);
void                 clear_keyboard(void);
void                 eeconfig_update_default_layer(layer_state_t state);
void                 eeconfig_disable(void);
void                 soft_reset_keyboard(void);
uint32_t             timer_read32(void);
uint32_t             timer_elapsed32(uint32_t start);
matrix_row_t         matrix_get_row(uint8_t row);
uint32_t             eeconfig_update_user_datablock(const void *data, uint32_t offset, uint32_t length);
uint32_t             eeconfig_read_user_datablock(void *data, uint32_t offset, uint32_t length);
void                 rgb_matrix_enable(void);
bool                 rgb_matrix_is_enabled(void);
void                 rgb_matrix_mode(uint8_t mode);
uint8_t              rgb_matrix_get_mode(void);
void                 rgb_matrix_sethsv(uint16_t h, uint8_t s, uint8_t v);
hsv_t                rgb_matrix_get_hsv(void);
void                 rgb_matrix_step(void);
rgb_t                hsv_to_rgb_nocie(hsv_t colour);

typedef union {
    uint8_t raw;
    struct {
        bool num_lock : 1;
        bool caps_lock : 1;
    };
} led_t;
typedef struct {
    uint32_t mode;
    void (*callback)(void);
} PWMChannelConfig;
typedef struct {
    uint32_t frequency;
    uint16_t period;
    void (*callback)(void);
    PWMChannelConfig channels[4];
} PWMConfig;
typedef struct {
    bool             started;
    uint16_t         width[4];
    const PWMConfig *config;
} PWMDriver;
extern PWMDriver PWMD_GPTM0, PWMD_MCTM0;
#define PWM_OUTPUT_DISABLED 0
#define PWM_OUTPUT_ACTIVE_LOW 1
#define PAL_MODE_OUTPUT_PUSHPULL 1
#define PAL_MODE_HT32_AF(n) ((n) << 8)
#define A14 14
#define C4 36
#define C5 37
#define C8 40
#define LED_CAPS_LOCK_PIN C8
void pwmStart(PWMDriver *driver, const PWMConfig *config);
void pwmEnableChannel(PWMDriver *driver, unsigned channel, uint16_t width);
void palSetLineMode(unsigned pin, unsigned mode);
void suspend_power_down_user(void);
void suspend_wakeup_init_user(void);
bool shutdown_user(bool bootloader);
void wait_ms(unsigned ms);

typedef struct {
    uint8_t iter, flags;
    bool    init;
} effect_params_t;
uint8_t rgb_matrix_get_val(void);
rgb_t   rgb_matrix_hsv_to_rgb(hsv_t colour);
void    rgb_matrix_set_color(unsigned index, uint8_t red, uint8_t green, uint8_t blue);
bool    rgb_matrix_check_finished_leds(unsigned last);
uint8_t scale8(uint8_t value, uint8_t scale);
