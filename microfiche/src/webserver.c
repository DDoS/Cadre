#include "webserver.h"

#include "image_handler.h"
#include "cors_preflight_handler.h"

#include <pico/cyw43_arch.h>

#include <picow_http/http.h>

void init_webserver(struct sync_encre_file *encre_file_sync) {
    struct server_cfg config = http_default_cfg();
    config.idle_tmo_s = 30;

    static const char *image_handler_path = "/image";
    err_t err = {};
    if ((err = register_image_handler(&config, image_handler_path, encre_file_sync)) != ERR_OK) {
        HTTP_LOG_ERROR("register_image_handler: %d\n", err);
    }
    if ((err = register_cors_preflight_handler(&config)) != ERR_OK) {
        HTTP_LOG_ERROR("register_image_handler: %d\n", err);
    }

    struct server *srv = NULL;
    while ((err = http_srv_init(&srv, &config)) != ERR_OK) {
        HTTP_LOG_ERROR("http_srv_init: %d\n", err);
    }

    while (true) {
        cyw43_arch_poll();
        cyw43_arch_wait_for_work_until(make_timeout_time_ms(1));
    }
}
