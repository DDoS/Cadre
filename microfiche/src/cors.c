#include "cors.h"

#include <pico/cyw43_arch.h>

#include <picow_http/http.h>

void set_cors_headers(struct http *connection) {
    size_t origin_size = {};
    const char *origin = http_req_hdr_str(&connection->req, "Origin", &origin_size);
    if (!origin || strcmp(origin, "null") == 0) {
        return;
    }

    // Match r"^http://.+\.local"
    static const char http_prefix[] = "http://";
    const size_t http_prefix_size = strlen(http_prefix);
    static const char local_suffix[] = ".local";
    const size_t local_suffix_size = strlen(local_suffix);

    bool valid_origin = false;
    if (strncmp(origin, "http://localhost", origin_size) == 0 ||
            strncmp(origin, "https://microfiche.sapon.ca", origin_size) == 0) {
        valid_origin = true;
    } else if (origin_size > http_prefix_size + local_suffix_size &&
            strncmp(origin, http_prefix, http_prefix_size) == 0 &&
            strncmp(origin + origin_size - local_suffix_size, local_suffix, local_suffix_size) == 0) {
        valid_origin = true;
    }
    if (valid_origin) {
        http_resp_set_hdr_ltrl(&connection->resp, "Access-Control-Allow-Origin", origin);
    }
}

static void bytes_to_hex(const uint8_t *bytes, size_t size, char* hex) {
    for (size_t i = 0; i < size; i++) {
        hex[i * 2 + 0] = 'A' + (bytes[i] & 0xF);
        hex[i * 2 + 1] = 'A' + ((bytes[i] >> 4) & 0xF);
    }
}

void set_cors_preflight_headers(struct http *connection) {
    http_resp_set_hdr_str(&connection->resp, "Access-Control-Allow-Methods", "POST, GET, OPTIONS");
    http_resp_set_hdr_str(&connection->resp, "Access-Control-Allow-Headers", "Content-Type");
    http_resp_set_hdr_str(&connection->resp, "Access-Control-Max-Age", "86400");
    http_resp_set_hdr_str(&connection->resp, "Access-Control-Allow-Private-Network", "true");

    cyw43_arch_lwip_begin();
    {
        struct netif *n = &cyw43_state.netif[CYW43_ITF_STA];
        http_resp_set_hdr_str(&connection->resp, "Private-Network-Access-Name", netif_get_hostname(n));

        uint8_t mac_address[6] = {};
        cyw43_ll_wifi_get_mac(&cyw43_state.cyw43_ll, mac_address);
        char hex_mac_address[sizeof(mac_address) * 2] = {};
        bytes_to_hex(mac_address, sizeof(mac_address), hex_mac_address);
        http_resp_set_hdr_str(&connection->resp, "Private-Network-Access-ID", hex_mac_address);
    }
    cyw43_arch_lwip_end();
}
