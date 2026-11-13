// SPDX-License-Identifier: GPL-2.0-or-later
#include "keyboards/mistel/md770rgb_bt/md770rgb_bt.h"
#include "keyboards/mistel/md770rgb_bt/keymaps/default/keymap.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

bool          process_record_user(uint16_t code, keyrecord_t *record);
void          housekeeping_task_user(void);
void          eeconfig_init_user_datablock(void);
layer_state_t default_layer_state_set_user(layer_state_t state);
extern hsv_t  md770_custom_colours[RGB_MATRIX_LED_COUNT];

layer_state_t       default_layer_state = 1, layer_state;
led_config_t        g_led_config;
static matrix_row_t matrix[MATRIX_ROWS];
static uint32_t     now;
static unsigned     resets, rewrites, saves;
static uint8_t      indicator;
static uint8_t      stored[RGB_MATRIX_LED_COUNT * 3];
static hsv_t        hsv = {85, 255, 64};
static uint8_t      effect;
static bool         enabled;
static rgb_t        rendered[RGB_MATRIX_LED_COUNT];

uint8_t rgb_matrix_get_val(void) {
    return hsv.v;
}
rgb_t rgb_matrix_hsv_to_rgb(hsv_t colour) {
    return hsv_to_rgb_nocie(colour);
}
void rgb_matrix_set_color(unsigned index, uint8_t red, uint8_t green, uint8_t blue) {
    assert(index < RGB_MATRIX_LED_COUNT);
    rendered[index] = (rgb_t){red, green, blue};
}
bool rgb_matrix_check_finished_leds(unsigned last) {
    return last == RGB_MATRIX_LED_COUNT;
}
uint8_t scale8(uint8_t value, uint8_t scale) {
    return (uint16_t)value * (scale + 1) >> 8;
}

#define RGB_MATRIX_EFFECT(name)
#define RGB_MATRIX_CUSTOM_EFFECT_IMPLS
#define RGB_MATRIX_USE_LIMITS(first, last)          \
    uint8_t first = 0, last = RGB_MATRIX_LED_COUNT; \
    (void)params
#define RGB_MATRIX_TEST_LED_FLAGS()
#include "keyboards/mistel/md770rgb_bt/keymaps/default/rgb_matrix_user.inc"

uint8_t get_highest_layer(layer_state_t state) {
    uint8_t layer = 0;
    while (state >>= 1)
        ++layer;
    return layer;
}
void default_layer_set(layer_state_t state) {
    default_layer_state = default_layer_state_set_user(state);
}
bool layer_state_is(uint8_t layer) {
    return (layer_state & (1UL << layer)) != 0;
}
void clear_keyboard(void) {}
void eeconfig_update_default_layer(layer_state_t state) {
    (void)state;
}
void eeconfig_disable(void) {}
void soft_reset_keyboard(void) {
    ++resets;
}
uint32_t timer_read32(void) {
    return now;
}
uint32_t timer_elapsed32(uint32_t start) {
    return now - start;
}
matrix_row_t matrix_get_row(uint8_t row) {
    return matrix[row];
}
void md770_set_layer_led(uint8_t colour) {
    indicator = colour;
}
uint32_t eeconfig_update_user_datablock(const void *data, uint32_t offset, uint32_t length) {
    assert(offset + length <= sizeof(stored));
    memcpy(stored + offset, data, length);
    ++saves;
    return length;
}
uint32_t eeconfig_read_user_datablock(void *data, uint32_t offset, uint32_t length) {
    assert(offset + length <= sizeof(stored));
    memcpy(data, stored + offset, length);
    return length;
}
void rgb_matrix_enable(void) {
    enabled = true;
}
bool rgb_matrix_is_enabled(void) {
    return enabled;
}
void rgb_matrix_mode(uint8_t mode) {
    effect = mode;
}
uint8_t rgb_matrix_get_mode(void) {
    return effect;
}
void rgb_matrix_sethsv(uint16_t h, uint8_t s, uint8_t v) {
    hsv = (hsv_t){h, s, v};
}
hsv_t rgb_matrix_get_hsv(void) {
    return hsv;
}
void rgb_matrix_step(void) {
    ++effect;
}
rgb_t hsv_to_rgb_nocie(hsv_t colour) {
    return (rgb_t){colour.h, colour.s, colour.v};
}
void dynamic_keymap_set_keycode(uint8_t layer, uint8_t row, uint8_t col, uint16_t code) {
    assert(layer == PROFILE2 && row < MATRIX_ROWS && col < MATRIX_COLS && code == KC_TRNS);
    ++rewrites;
}
uint16_t keycode_at_keymap_location_raw(uint8_t layer, uint8_t row, uint8_t col) {
    (void)layer;
    (void)row;
    (void)col;
    return KC_TRNS;
}

static bool event(uint16_t code, uint8_t row, uint8_t col, bool pressed) {
    keyrecord_t record = {.event = {.type = KEY_EVENT, .key = {.row = row, .col = col}, .pressed = pressed}};
    return process_record_user(code, &record);
}
static void toggle_edit(void) {
    assert(!event(MD770_RGB_EDIT, 2, 6, true));
    assert(!event(MD770_RGB_EDIT, 2, 6, false));
}

int main(void) {
    memset(g_led_config.matrix_co, UINT8_MAX, sizeof(g_led_config.matrix_co));
    g_led_config.matrix_co[12][2] = 0;
    eeconfig_init_user_datablock();
    saves = 0;

    assert(event(MO(FN), 2, 4, true));
    assert(event(KC_B, 15, 4, true));
    toggle_edit();
    assert(indicator == 7 && enabled && effect == RGB_MATRIX_CUSTOM_MD770_CUSTOM);
    assert(event(MO(FN), 2, 4, false));
    assert(event(KC_B, 15, 4, false));

    keyrecord_t synthetic = {.event = {.key = {.row = 251, .col = 0}, .type = 6, .pressed = false}};
    assert(process_record_user(KC_A, &synthetic));
    synthetic.event.type = 4;
    synthetic.event.key.row = 0;
    synthetic.event.pressed = true;
    assert(process_record_user(KC_A, &synthetic));
    synthetic.event.type = KEY_EVENT;
    synthetic.event.key.row = 255;
    synthetic.event.key.col = 255;
    assert(process_record_user(KC_A, &synthetic));
    assert(md770_custom_colours[0].v == 0);

    layer_state = 1UL << PN;
    assert(!event(KC_A, 12, 2, true));
    assert(md770_custom_colours[0].v == 0);
    layer_state = 0;
    assert(!event(KC_A, 12, 2, false));
    assert(event(RM_VALU, 5, 4, true));
    assert(event(RM_VALU, 5, 4, false));
    assert(event(QK_BOOT, 6, 6, true));
    assert(event(QK_BOOT, 6, 6, false));

    assert(!event(KC_A, 12, 2, true));
    assert(md770_custom_colours[0].h == 85 && md770_custom_colours[0].v == 255);
    toggle_edit();
    assert(saves == 1 && indicator == 0 && stored[2] == 255);
    assert(!event(KC_A, 12, 2, false));
    assert(event(KC_A, 12, 2, true));
    assert(event(KC_A, 12, 2, false));

    toggle_edit();
    assert(!event(KC_A, 12, 2, true));
    assert(!event(KC_A, 12, 2, false));
    assert(md770_custom_colours[0].v == 0);
    assert(!event(KC_LALT, 12, 4, true));
    assert(!event(KC_LALT, 12, 4, false));
    assert(!event(KC_RALT, 1, 4, true));
    now += 2000;
    housekeeping_task_user();
    assert(resets == 0);
    assert(!event(KC_RALT, 1, 4, false));
    toggle_edit();

    toggle_edit();
    unsigned prior_saves = saves;
    assert(!event(MD770_RGB_NEXT, 0, 6, true));
    assert(saves == prior_saves + 1 && indicator == 0);
    assert(event(KC_A, 12, 2, true));
    assert(event(KC_A, 12, 2, false));
    toggle_edit();
    prior_saves = saves;
    rgb_matrix_mode(RGB_MATRIX_SOLID_COLOR);
    housekeeping_task_user();
    assert(saves == prior_saves + 1 && indicator == 0);
    assert(event(KC_A, 12, 2, true));
    assert(event(KC_A, 12, 2, false));

    default_layer_set((1UL << BASE) | (1UL << PROFILE2));
    assert(indicator == 2);
    matrix[2] = 1;
    assert(!event(MD770_RESET_PROFILE, 10, 2, true));
    now += 1000;
    housekeeping_task_user();
    assert(rewrites == 0);
    assert(!event(MD770_RESET_PROFILE, 10, 2, false));
    housekeeping_task_user();
    assert(rewrites == 0);
    matrix[2] = 0;
    housekeeping_task_user();
    assert(rewrites == MATRIX_ROWS * MATRIX_COLS && indicator == 7);
    now += 500;
    housekeeping_task_user();
    assert(indicator == 2);

    assert(event(KC_LALT, 12, 4, true));
    assert(event(KC_RALT, 1, 4, true));
    now += 999;
    housekeeping_task_user();
    assert(resets == 0);
    now += 1;
    housekeeping_task_user();
    assert(resets == 1);
    housekeeping_task_user();
    assert(resets == 1);
    assert(event(KC_LALT, 12, 4, false));
    assert(event(KC_RALT, 1, 4, false));
    memset(g_led_config.matrix_co, UINT8_MAX, sizeof(g_led_config.matrix_co));
    const uint8_t positions[][2] = {{15, 2}, {12, 2}, {12, 3}, {11, 2}, {5, 4}, {3, 4}, {0, 5}, {6, 3}, {13, 2}};
    for (unsigned i = 0; i < ARRAY_SIZE(positions); ++i)
        g_led_config.matrix_co[positions[i][0]][positions[i][1]] = i;
    effect_params_t params = {0};
    assert(MD770_CUSTOM(&params));
    assert(MD770_WASD(&params));
    for (unsigned i = 0; i < RGB_MATRIX_LED_COUNT; ++i) {
        assert(rendered[i].b == (i < 8 ? hsv.v : 0));
    }
    puts("RGB editing releases, saved colours, WASD positions, held-key profile reset and factory reset passed.");
}
