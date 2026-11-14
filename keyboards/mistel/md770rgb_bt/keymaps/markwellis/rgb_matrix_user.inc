// Copyright 2026 Mark Ellis (@markwellis)
// SPDX-License-Identifier: GPL-2.0-or-later
RGB_MATRIX_EFFECT(MD770_CUSTOM)
RGB_MATRIX_EFFECT(MD770_WASD)

#ifdef RGB_MATRIX_CUSTOM_EFFECT_IMPLS
extern hsv_t md770_custom_colours[RGB_MATRIX_LED_COUNT];

static bool MD770_CUSTOM(effect_params_t *params) {
    RGB_MATRIX_USE_LIMITS(led_min, led_max);
    for (uint8_t i = led_min; i < led_max; ++i) {
        RGB_MATRIX_TEST_LED_FLAGS();
        hsv_t colour = md770_custom_colours[i];
        colour.v     = scale8(colour.v, rgb_matrix_get_val());
        rgb_t rgb    = rgb_matrix_hsv_to_rgb(colour);
        rgb_matrix_set_color(i, rgb.r, rgb.g, rgb.b);
    }
    return rgb_matrix_check_finished_leds(led_max);
}

static bool MD770_WASD(effect_params_t *params) {
    RGB_MATRIX_USE_LIMITS(led_min, led_max);
    rgb_t rgb = rgb_matrix_hsv_to_rgb(rgb_matrix_get_hsv());
    for (uint8_t i = led_min; i < led_max; ++i) {
        RGB_MATRIX_TEST_LED_FLAGS();
        bool highlight = i == g_led_config.matrix_co[15][2] || i == g_led_config.matrix_co[12][2] || i == g_led_config.matrix_co[12][3] || i == g_led_config.matrix_co[11][2] || i == g_led_config.matrix_co[5][4] || i == g_led_config.matrix_co[3][4] || i == g_led_config.matrix_co[0][5] || i == g_led_config.matrix_co[6][3];
        rgb_matrix_set_color(i, highlight ? rgb.r : 0, highlight ? rgb.g : 0, highlight ? rgb.b : 0);
    }
    return rgb_matrix_check_finished_leds(led_max);
}
#endif
