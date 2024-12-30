#include "wifi.h"

#include <pico/flash.h>
#include <pico/cyw43_arch.h>
#include <hardware/flash.h>

#include <lwip/apps/mdns.h>

void setup_hostname(const char *hostname) {
    cyw43_arch_lwip_begin();
    struct netif *n = &cyw43_state.netif[CYW43_ITF_STA];
    netif_set_hostname(n, hostname);
    netif_set_up(n);
    mdns_resp_init();
    mdns_resp_add_netif(n, hostname);
    cyw43_arch_lwip_end();
}

enum {
    max_ssid_length = sizeof(((cyw43_ev_scan_result_t *)NULL)->ssid) / sizeof(uint8_t),
    max_password_length = 63,
};

typedef struct {
    uint8_t (*names)[max_ssid_length + 1];
    size_t count;
} network_list;

static int scan_result(void *env, const cyw43_ev_scan_result_t *result) {
    network_list *networks = env;

    for (size_t i = 0; i < networks->count; i++) {
        if (memcmp(networks->names[i], result->ssid, result->ssid_len) == 0) {
            return 0;
        }
    }

    networks->names = realloc(networks->names, (networks->count + 1) * sizeof(networks->names[0]));
    memcpy(networks->names[networks->count], result->ssid, result->ssid_len);
    networks->names[networks->count][result->ssid_len] = '\0';
    networks->count += 1;
    return 0;
}

static const uint8_t saved_network_magic[] = "sn6PlpTmM7bdOCmnbr";

struct saved_network {
    uint8_t magic[sizeof(saved_network_magic)];
    uint8_t ssid[max_ssid_length + 1];
    uint8_t password[max_password_length + 1];
};

static const uint32_t saved_network_flash_offset = PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE;

static void read_saved_network(struct saved_network* network) {
    *network = *(const struct saved_network *)(uintptr_t)(XIP_BASE +saved_network_flash_offset);
}

static bool is_valid_saved_network(struct saved_network* network) {
    if (memcmp(network->magic, saved_network_magic, sizeof(saved_network_magic)) != 0) {
        return false;
    }

    const uint8_t *byte_ptr = (const uint8_t *)network;
    for (size_t i = 0; i < sizeof(struct saved_network); i++) {
        if (*(byte_ptr + i) != 0xFFu) {
            return true;
        }
    }

    return false;
}

static uint32_t find_first_free_page() {
    uint32_t page_offset = 0;
    for (; page_offset < FLASH_SECTOR_SIZE; page_offset += FLASH_PAGE_SIZE) {
        const uintptr_t address = XIP_BASE + saved_network_flash_offset + page_offset;
        struct saved_network *network = (struct saved_network *)address;
        if (!is_valid_saved_network(network)) {
            break;
        }
    }

    return page_offset;
}

static void call_flash_range_erase(void *params) {
    const uint32_t offset = (uint32_t)(uintptr_t)params;
    flash_range_erase(offset, FLASH_SECTOR_SIZE);
}

static void call_flash_range_program(void *params) {
    const uint32_t offset = ((uintptr_t*)params)[0];
    const uint8_t *data = (const uint8_t *)((uintptr_t*)params)[1];
    flash_range_program(offset, data, FLASH_PAGE_SIZE);
}

static bool write_network(struct saved_network* network) {
    uint32_t page_offset = find_first_free_page();
    if (page_offset == FLASH_SECTOR_SIZE) {
        if (flash_safe_execute(&call_flash_range_erase,
            (void *)saved_network_flash_offset, UINT32_MAX) != PICO_OK) {
            return false;
        }
        page_offset = 0;
    }

    memcpy(network->magic, saved_network_magic, sizeof(saved_network_magic));

    uintptr_t program_params[] = {
        saved_network_flash_offset + page_offset,
        (uintptr_t)network,
    };
    if (flash_safe_execute(&call_flash_range_program, program_params,
             UINT32_MAX) != PICO_OK) {
        return false;
    }

    struct saved_network saved_network;
    read_saved_network(&saved_network);
    return memcmp(network, &saved_network, sizeof(struct saved_network)) == 0;
}

enum wifi_status init_wifi() {
    if (cyw43_arch_init() != 0) {
        printf("Network architecture initialization failed\n");
        return wifi_status_connection_failed;
    }

    cyw43_arch_enable_sta_mode();

    if (cyw43_wifi_pm(&cyw43_state, CYW43_NONE_PM) != 0) {
        printf("Failed to disable wifi power management\n");
    }

    setup_hostname("microfiche");

    bool new_network = false;
    struct saved_network network;
    read_saved_network(&network);
    if (!is_valid_saved_network(&network)) {
        printf("Saved network is invalid, asking for a new network\n");
        new_network = true;

        printf("Wifi scan started\n");
        cyw43_wifi_scan_options_t scan_options = {};
        network_list networks = {};
        if (cyw43_wifi_scan(&cyw43_state, &scan_options, &networks, &scan_result) != 0) {
            return wifi_status_connection_failed;
        }

        while (cyw43_wifi_scan_active(&cyw43_state)) {
            cyw43_arch_poll();
            cyw43_arch_wait_for_work_until(make_timeout_time_ms(1000));
        }

        if (networks.count <= 0) {
            return wifi_status_no_network;
        }

        printf("Wifi networks found:\n");
        for (size_t i = 0; i < networks.count; i++) {
            printf("  %u: %s\n", i, networks.names[i]);
        }

        size_t index = 0;
        printf("Enter network index: ");
        scanf("%u", &index);
        if (index >= networks.count) {
            return wifi_status_no_network;
        }

        memcpy(network.ssid, networks.names[index], max_ssid_length + 1);
        free(networks.names);

        printf("Enter network password: ");
        scanf("%63s", network.password);
    }

    bool connected = false;
    int connect_retries = 0;
    do {
        printf("Connecting to \"%s\" with password \"%s\" (retry %d) ...\n", network.ssid, network.password, connect_retries + 1);
        if (cyw43_arch_wifi_connect_timeout_ms((const char *)network.ssid, (const char *)network.password,
            CYW43_AUTH_WPA2_AES_PSK, 10000) == 0) {
            connected = true;
            break;
        }
    } while (++connect_retries < 5);

    if (!connected) {
        printf("Failed to connect after %d retries\n", connect_retries);
        return wifi_status_connection_failed;
    }

    printf("Connected to \"%s\"\n", network.ssid);

    if (new_network) {
        bool wrote_new_network = false;
        for (int i = 0; i < 3; i++) {
            if (write_network(&network)) {
                wrote_new_network = true;
                break;
            }
        }

        if (!wrote_new_network) {
            printf("Failed to write the new network\n");
        }
    }

    return wifi_status_connected;
}
