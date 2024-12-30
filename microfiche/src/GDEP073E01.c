#include "GDEP073E01.h"

#include <hardware/gpio.h>
#include <hardware/spi.h>
#include <pico/time.h>

#define DC_PIN 22
#define RESET_PIN 21
#define BUSY_PIN 20

#define BLACK 0
#define WHITE 1
#define YELLOW 2
#define RED 3
// Actually 4 is unused
#define BLUE 4 // Actually 5
#define GREEN 5 // Actually 6

#define CMD_PSR 0x00
#define CMD_PWR 0x01
#define CMD_POF 0x02
#define CMD_POFS 0x03
#define CMD_PON 0x04
#define CMD_BTST1 0x05
#define CMD_BTST2 0x06
#define CMD_DSLP 0x07
#define CMD_BTST3 0x08
#define CMD_DTM 0x10
#define CMD_DRF 0x12
#define CMD_IPC 0x13
#define CMD_PLL 0x30
#define CMD_TSE 0x41
#define CMD_CDI 0x50
#define CMD_TCON 0x60
#define CMD_TRES 0x61
#define CMD_VDCS 0x82
#define CMD_T_VDCS 0x84
#define CMD_AGID 0x86
#define CMD_CMDH 0xAA
#define CMD_CCSET 0xE0
#define CMD_PWS 0xE3
#define CMD_TSSET 0xE6

#define SPI_COMMAND false
#define SPI_DATA true

static void setup_pin(uint pin, enum gpio_dir direction, bool initial) {
    gpio_init(pin);
    gpio_set_dir(pin, direction);
    if (direction == GPIO_OUT) {
        gpio_put(pin, initial);
    }
}

static void busy_wait(uint32_t timeout_ms) {
    if (gpio_get(BUSY_PIN)) {
        sleep_ms(timeout_ms);
        return;
    }

    const uint64_t timeout_us = (uint64_t)timeout_ms * 1000;
    const uint64_t start_time = time_us_64();
    do {
        sleep_ms(10);
        if (time_us_64() - start_time >= timeout_us) {
            return;
        }
    } while (!gpio_get(BUSY_PIN));
}

static void write_to_spi(bool dc, const uint8_t *data, size_t length) {
    gpio_put(DC_PIN, dc);

    spi_write_blocking(spi0, data, length);
}

static void send_command(uint8_t command) {
    write_to_spi(SPI_COMMAND, &command, sizeof(command));
}

static void send_data(const uint8_t *data, size_t length) {
    write_to_spi(SPI_DATA, data, length);
}

#define send_command_with_data(command, ...) \
    do { \
        send_command(command); \
        const uint8_t cmd_data[] = {__VA_ARGS__}; \
        send_data(cmd_data, sizeof(cmd_data)); \
    } while (false)

static void setup() {
    static bool initialized = false;
    if (!initialized) {
        setup_pin(DC_PIN, GPIO_OUT, false);
        setup_pin(RESET_PIN, GPIO_OUT, true);
        setup_pin(BUSY_PIN, GPIO_IN, false);

        gpio_set_function(19, GPIO_FUNC_SPI);
        gpio_set_function(18, GPIO_FUNC_SPI);
        gpio_set_function(17, GPIO_FUNC_SPI);
        gpio_set_function(16, GPIO_FUNC_SPI);
        spi_init(spi0, 5000000);

        initialized = true;
    }

    gpio_put(RESET_PIN, false);
    sleep_ms(100);
    gpio_put(RESET_PIN, true);
    sleep_ms(100);
    gpio_put(RESET_PIN, false);
    sleep_ms(100);
    gpio_put(RESET_PIN, true);

    busy_wait(1000);

    send_command_with_data(CMD_CMDH, 0x49, 0x55, 0x20, 0x08, 0x09, 0x18);
    send_command_with_data(CMD_PWR, 0x3F, 0x00, 0x32, 0x2A, 0x0E, 0x2A);
    send_command_with_data(CMD_PSR, 0x5F, 0x69);
    send_command_with_data(CMD_POFS, 0x00, 0x54, 0x00, 0x44);
    send_command_with_data(CMD_BTST1, 0x40, 0x1F, 0x1F, 0x2C);
    send_command_with_data(CMD_BTST2, 0x6F, 0x1F, 0x16, 0x25);
    send_command_with_data(CMD_BTST3, 0x6F, 0x1F, 0x1F, 0x22);
    send_command_with_data(CMD_IPC, 0x00, 0x04);
    send_command_with_data(CMD_PLL, 0x02);
    send_command_with_data(CMD_TSE, 0x00);
    send_command_with_data(CMD_CDI, 0x3F);
    send_command_with_data(CMD_TCON, 0x02, 0x00);
    send_command_with_data(CMD_TRES, 0x03, 0x20, 0x01, 0xE0);
    send_command_with_data(CMD_VDCS, 0x1E);
    send_command_with_data(CMD_T_VDCS, 0x01);
    send_command_with_data(CMD_AGID, 0x00);
    send_command_with_data(CMD_PWS, 0x2F);
    send_command_with_data(CMD_CCSET, 0x00);
    send_command_with_data(CMD_TSSET, 0x00);
}

void GDEP073E01_write_image(const uint8_t *color_bits) {
    setup();

    send_command(CMD_DTM);

    const uint8_t color_mask = (1 << GDEP073E01_BITS_PER_COLOR) - 1;
    uint8_t color_pair = 0;
    for (uint32_t i = 0, bit_index = 0; i < GDEP073E01_WIDTH * GDEP073E01_HEIGHT;
            i++, bit_index += GDEP073E01_BITS_PER_COLOR) {
        const uint32_t byte_index = bit_index >> 3;
        const uint32_t bit_offset = bit_index & 7;
        uint32_t color = (color_bits[byte_index] >> bit_offset) & color_mask;

        const uint32_t next_byte_index = (bit_index + GDEP073E01_BITS_PER_COLOR) >> 3;
        if (byte_index != next_byte_index) {
            const uint32_t next_bit_offset = 8 - bit_offset;
            const uint32_t next_mask = color_mask >> next_bit_offset << next_bit_offset;
            color |= (color_bits[next_byte_index] << next_bit_offset) & next_mask;
        }

        color = MAX(MIN(color, 5), 0);
        if (color >= 4) {
            color++;
        }

        color_pair = (color_pair << 4) | color;

        if (i & 1) {
            send_data(&color_pair, sizeof(color_pair));
        }
    }

    send_command(CMD_PON);
    busy_wait(400);

    send_command_with_data(CMD_DRF, 0x00);
    busy_wait(45000);

    send_command_with_data(CMD_POF, 0x00);
    busy_wait(400);

    send_command_with_data(CMD_DSLP, 0xA5);
}
