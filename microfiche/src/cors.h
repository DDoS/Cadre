#pragma once

struct http;

void set_cors_headers(struct http *connection);

void set_cors_preflight_headers(struct http *connection);
