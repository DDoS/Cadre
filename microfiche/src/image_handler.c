#include "image_handler.h"

#include "encre_file.h"
#include "cors.h"

#include <picow_http/http.h>

static struct http *current_connection = NULL;

static struct sync_encre_file encre_file_events;

err_t image_handler(struct http *connection, void *data) {
    struct encre_file_context *file_context = data;

    const size_t start_offset = http_req_curr_body_off(&connection->req);
    const size_t total_size = http_req_body_len(&connection->req);

    if (!start_offset) {
        if (total_size > sizeof(file_context->file)) {
            return http_resp_err(connection, HTTP_STATUS_CONTENT_TOO_LARGE);
        }

        if (!encre_file_events.acquire()) {
            return http_resp_err(connection, HTTP_STATUS_CONFLICT);
        }

        begin_encre_file(file_context);
        current_connection = connection;
    } else if (current_connection != connection) {
        return http_resp_err(connection, HTTP_STATUS_CONFLICT);
    }

    for (size_t offset = start_offset, size_increment = 0; offset < total_size; offset += size_increment) {
        const uint8_t *buffer;
        err_t err;
        if ((err = http_req_body_ptr(connection, &buffer, &size_increment, offset)) != ERR_OK) {
            if (err == ERR_INPROGRESS) {
                return ERR_OK;
            }

            HTTP_LOG_ERROR("http_req_body_ptr(): %d", err);
            return http_resp_err(connection, HTTP_STATUS_INTERNAL_SERVER_ERROR);
        }

        if (!size_increment) {
            break;
        }

        if (!continue_encre_file(file_context, buffer, size_increment)) {
            return http_resp_err(connection, HTTP_STATUS_BAD_REQUEST);
        }
    }

    if (!file_context->read_colors) {
        return http_resp_err(connection, HTTP_STATUS_BAD_REQUEST);
    }

    encre_file_events.finish(&file_context->file);

    set_cors_headers(connection);
    http_resp_set_status(http_resp(connection), HTTP_STATUS_NO_CONTENT);
    http_resp_send_hdr(connection);
    return ERR_OK;
}

static struct encre_file_context file_context;

err_t register_image_handler(struct server_cfg *config, const char *path,
        struct sync_encre_file *encre_file_sync) {
    encre_file_events = *encre_file_sync;
    return register_streamed_hndlr(config, path, &image_handler,
        HTTP_METHOD_POST, &file_context);
}
