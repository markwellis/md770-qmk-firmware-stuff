// SPDX-License-Identifier: GPL-2.0-or-later
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "flash_spi.h"
#include "wear_leveling.h"

static uint8_t flash[EXTERNAL_FLASH_SIZE];
static unsigned erases;
static uint32_t last_erased;

void flash_init(void) {}
flash_status_t flash_erase_block(uint32_t address) {
    assert(address % EXTERNAL_FLASH_BLOCK_SIZE == 0);
    assert(address == 0 && EXTERNAL_FLASH_BLOCK_SIZE == 65536);
    last_erased = address;
    ++erases;
    memset(flash + address, 0xff, EXTERNAL_FLASH_BLOCK_SIZE);
    return FLASH_STATUS_SUCCESS;
}
flash_status_t flash_read_range(uint32_t address, void *data, size_t length) {
    assert(address + length <= WEAR_LEVELING_BACKING_SIZE);
    memcpy(data, flash + address, length);
    return FLASH_STATUS_SUCCESS;
}
flash_status_t flash_write_range(uint32_t address, const void *data, size_t length) {
    assert(address + length <= WEAR_LEVELING_BACKING_SIZE);
    const uint8_t *bytes = data;
    for (size_t i = 0; i < length; ++i) flash[address + i] &= bytes[i];
    return FLASH_STATUS_SUCCESS;
}

int main(void) {
    memset(flash, 0xa5, sizeof(flash));
    assert(wear_leveling_erase() != WEAR_LEVELING_FAILED);
    assert(erases == 1 && last_erased == 0);
    for (size_t i = 0; i < EXTERNAL_FLASH_BLOCK_SIZE; ++i) assert(flash[i] == 0xff);
    for (size_t i = EXTERNAL_FLASH_BLOCK_SIZE; i < sizeof(flash); ++i) assert(flash[i] == 0xa5);
    assert(wear_leveling_init() != WEAR_LEVELING_FAILED);
    const uint8_t profile = 9;
    const uint8_t colours[] = {85, 255, 255, 170, 255, 255};
    assert(wear_leveling_write(3, &profile, sizeof(profile)) != WEAR_LEVELING_FAILED);
    assert(wear_leveling_write(48, colours, sizeof(colours)) != WEAR_LEVELING_FAILED);
    assert(wear_leveling_init() != WEAR_LEVELING_FAILED);
    uint8_t saved_profile = 0, saved_colours[sizeof(colours)] = {0};
    assert(wear_leveling_read(3, &saved_profile, sizeof(saved_profile)) != WEAR_LEVELING_FAILED);
    assert(wear_leveling_read(48, saved_colours, sizeof(saved_colours)) != WEAR_LEVELING_FAILED);
    assert(saved_profile == profile && memcmp(saved_colours, colours, sizeof(colours)) == 0);
    for (unsigned i = 0; i < 1000; ++i) {
        uint16_t value = i;
        assert(wear_leveling_write(1024, &value, sizeof(value)) != WEAR_LEVELING_FAILED);
    }
    assert(erases > 1);
    assert(wear_leveling_init() != WEAR_LEVELING_FAILED);
    uint16_t last = 0;
    assert(wear_leveling_read(1024, &last, sizeof(last)) != WEAR_LEVELING_FAILED);
    assert(last == 999);
    assert(wear_leveling_read(48, saved_colours, sizeof(saved_colours)) != WEAR_LEVELING_FAILED);
    assert(memcmp(saved_colours, colours, sizeof(colours)) == 0);
    for (size_t i = EXTERNAL_FLASH_BLOCK_SIZE; i < sizeof(flash); ++i) assert(flash[i] == 0xa5);
    puts("Native block erasure, cold reload, journal consolidation and allocation bounds passed.");
}
