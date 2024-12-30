#pragma once

#include <stdbool.h>

struct encre_file;

typedef bool (*encre_file_acquire)();
typedef void (*encre_file_finish)(struct encre_file* file);

struct sync_encre_file {
    encre_file_acquire acquire;
    encre_file_finish finish;
};

void init_webserver(struct sync_encre_file *encre_file_sync);
