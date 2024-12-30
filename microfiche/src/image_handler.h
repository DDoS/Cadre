#pragma once

#include "webserver.h"

#include <lwip/err.h>

struct server_cfg;

err_t register_image_handler(struct server_cfg *config, const char *path,
        struct sync_encre_file *encre_file_sync);
