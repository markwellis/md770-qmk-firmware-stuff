#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "quantum.h"
static matrix_row_t physical[8];
void md770_scan_copy(matrix_row_t rows[8]) { memcpy(rows, physical, sizeof(physical)); }
void md770_link_task(matrix_row_t rows[MATRIX_ROWS]) { (void)rows; }
bool matrix_scan_custom(matrix_row_t rows[MATRIX_ROWS]);
int main(void) {
    matrix_row_t rows[MATRIX_ROWS] = {0};
    for (unsigned mask = 0; mask < 256; ++mask) {
        for (unsigned row = 0; row < 7; ++row) physical[row] = (matrix_row_t)(0x81U >> (row % 3));
        physical[7] = (matrix_row_t)mask;
        matrix_scan_custom(rows);
        if (rows[7] != (mask & 15U)) {
            fprintf(stderr, "DIP raw %02x became %02x, expected %02x\n", mask, rows[7], mask & 15U);
            return 1;
        }
        assert(memcmp(rows, physical, 7) == 0);
        for (unsigned row = 8; row < MATRIX_ROWS; ++row) assert(rows[row] == 0);
        assert(!matrix_scan_custom(rows));
    }
    puts("Actual matrix adapter: all 256 DIP bytes, local key rows and unchanged snapshots passed");
}
