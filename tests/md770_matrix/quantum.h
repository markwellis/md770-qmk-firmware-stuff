#pragma once
#include <stdbool.h>
#include <stdint.h>
#define MATRIX_ROWS 16
#define MATRIX_COLS 8
typedef uint8_t matrix_row_t;
extern int USBD1;
void usbDisconnectBus(void *device);
void wait_ms(unsigned ms);
void chSysDisable(void);
void __DSB(void);
void NVIC_SystemReset(void);
