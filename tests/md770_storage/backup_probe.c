// Copyright 2026 Mark Ellis (@markwellis)
// SPDX-License-Identifier: GPL-2.0-or-later
#include "quantum.h"
#include "spi_master.h"
#include "via.h"

void via_custom_value_command_kb(uint8_t *data, uint8_t length) {
    if (length != 32 || data[0] != id_custom_get_value || data[1] != 0x7f || data[2] != 0) {
        data[0] = id_unhandled;
        return;
    }
    uint32_t address = ((uint32_t)data[3] << 16) | ((uint32_t)data[4] << 8) | data[5];
    uint8_t  count   = data[6];
    data[7]          = 1;
    if (!count || count > 24 || address + count > 65536 + 64) {
        return;
    }
    if (spi_start(A9, false, 0, EXTERNAL_FLASH_SPI_CLOCK_DIVISOR)) {
        const uint8_t command[] = {0x03, address >> 16, address >> 8, address};
        if (spi_transmit(command, sizeof(command)) == SPI_STATUS_SUCCESS && spi_receive(data + 8, count) == SPI_STATUS_SUCCESS) {
            data[7] = 0;
        }
        spi_stop();
    }
}
