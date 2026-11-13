// SPDX-License-Identifier: GPL-2.0-or-later
#include "keyboards/mistel/md770rgb_bt/md770rgb_bt.h"
#include <assert.h>
#include <stdio.h>

void            led_init_ports(void);
void            led_update_ports(led_t state);
void            suspend_power_down_kb(void);
void            suspend_wakeup_init_kb(void);
bool            shutdown_kb(bool bootloader);
PWMDriver       PWMD_GPTM0, PWMD_MCTM0;
static unsigned pwm_writes, mode_writes, sleep_calls, wake_calls;
static unsigned modes[64];
static unsigned entry_edges;
static bool checking_entry;

void pwmStart(PWMDriver *driver, const PWMConfig *config) {
    assert(config->frequency == 24000000 && config->period == UINT16_MAX);
    driver->started = true;
    driver->config  = config;
}
void pwmEnableChannel(PWMDriver *driver, unsigned channel, uint16_t width) {
    assert(driver->started && channel < 4 && width <= 6000);
    driver->width[channel] = width;
    ++pwm_writes;
}
void palSetLineMode(unsigned pin, unsigned mode) {
    assert(pin < 64 && mode == (PAL_MODE_HT32_AF(4) | PAL_MODE_OUTPUT_PUSHPULL));
    modes[pin] = mode;
    ++mode_writes;
}
void suspend_power_down_user(void) {
    ++sleep_calls;
}
void suspend_wakeup_init_user(void) {
    ++wake_calls;
}
bool shutdown_user(bool bootloader) {
    (void)bootloader;
    return true;
}
void wait_ms(unsigned ms) {
    if (checking_entry) {
        assert(ms == 100);
        uint16_t expected = entry_edges++ % 2 ? 0 : 6000;
        assert(PWMD_GPTM0.width[0] == expected && PWMD_GPTM0.width[1] == expected);
        assert(PWMD_GPTM0.width[2] == expected && PWMD_MCTM0.width[0] == expected);
    } else {
        assert(ms == 250);
    }
}

int main(void) {
    md770_set_layer_led(2);
    led_update_ports((led_t){.caps_lock = true});
    assert(shutdown_kb(true));
    assert(pwm_writes == 0);
    md770_set_layer_led(2);
    led_init_ports();
    assert(mode_writes == 4 && modes[C4] && modes[C5] && modes[C8] && modes[A14]);
    assert(PWMD_GPTM0.config->channels[0].mode == PWM_OUTPUT_ACTIVE_LOW);
    assert(PWMD_GPTM0.config->channels[1].mode == PWM_OUTPUT_ACTIVE_LOW);
    assert(PWMD_GPTM0.config->channels[2].mode == PWM_OUTPUT_ACTIVE_LOW);
    assert(PWMD_GPTM0.config->channels[3].mode == PWM_OUTPUT_DISABLED);
    assert(PWMD_MCTM0.config->channels[0].mode == PWM_OUTPUT_ACTIVE_LOW);
    assert(PWMD_GPTM0.width[0] == 0 && PWMD_GPTM0.width[1] == 6000 && PWMD_GPTM0.width[2] == 0);
    led_update_ports((led_t){.caps_lock = true});
    md770_set_layer_led(4);
    assert(PWMD_GPTM0.width[1] == 0 && PWMD_GPTM0.width[2] == 6000 && PWMD_MCTM0.width[0] == 6000);
    suspend_power_down_kb();
    led_update_ports((led_t){0});
    assert(sleep_calls == 1 && PWMD_GPTM0.width[2] == 0 && PWMD_MCTM0.width[0] == 0);
    led_update_ports((led_t){.caps_lock = true});
    suspend_wakeup_init_kb();
    assert(wake_calls == 1 && PWMD_GPTM0.width[2] == 6000 && PWMD_MCTM0.width[0] == 6000);
    checking_entry = true;
    assert(shutdown_kb(true));
    checking_entry = false;
    assert(entry_edges == 6 && PWMD_GPTM0.width[2] == 0);
    assert(PWMD_GPTM0.width[0] == 0 && PWMD_GPTM0.width[1] == 0 && PWMD_MCTM0.width[0] == 0);
    assert(shutdown_kb(false));
    assert(PWMD_GPTM0.width[0] == 6000 && PWMD_GPTM0.width[1] == 6000 && PWMD_MCTM0.width[0] == 6000);
    puts("Indicator initialisation, PWM limits, Caps/profile independence and suspend/resume passed.");
}
