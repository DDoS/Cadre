#pragma once

#include <picow_http/http.h>

// https://wicg.github.io/private-network-access/#example-mixed-content
// https://github.com/explainers-by-googlers/local-network-access

err_t register_cors_preflight_handler(struct server_cfg *config);
