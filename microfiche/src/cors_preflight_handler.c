#include "cors_preflight_handler.h"

#include "cors.h"

err_t cors_preflight_handler(struct http *connection, void *data) {
    struct allow_pna *pna_allow = data;

    set_cors_headers(connection);
    set_cors_preflight_headers(connection);

    return ERR_OK;
}

err_t register_cors_preflight_handler(struct server_cfg *config) {
    return register_hndlr(config, "/", &cors_preflight_handler,
        HTTP_METHOD_OPTIONS, NULL);
}
