// Copyright 2026 Mark Ellis (@markwellis)
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#ifdef RGB_MATRIX_ENABLE
#    define EECONFIG_USER_DATA_SIZE (RGB_MATRIX_LED_COUNT * 3)
#endif
