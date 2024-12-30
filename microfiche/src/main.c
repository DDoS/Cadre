#include "wifi.h"
#include "encre_file.h"
#include "GDEP073E01.h"
#include "webserver.h"

#include <pico/stdio.h>
#include <pico/flash.h>
#include <pico/sem.h>
#include <pico/multicore.h>
#include <hardware/watchdog.h>

static semaphore_t receive_file_semaphore;
static semaphore_t display_file_semaphore;
static struct encre_file *shared_file = NULL;

static void core1_start() {
    flash_safe_execute_core_init();

    while (true) {
        sem_acquire_blocking(&display_file_semaphore);
        GDEP073E01_write_image(shared_file->body.colors);
        sem_release(&receive_file_semaphore);
    }
}

static bool on_acquire_encre_file() {
    if (!shared_file) {
        return true;
    }

    if (sem_acquire_timeout_ms(&receive_file_semaphore, 500)) {
        shared_file = NULL;
        return true;
    }

    return false;
}

static void on_encre_file_finish(struct encre_file* file) {
    shared_file = file;
    sem_release(&display_file_semaphore);
}

int main() {
    stdio_init_all();

    sem_init(&receive_file_semaphore, 0, 1);
    sem_init(&display_file_semaphore, 0, 1);

    multicore_launch_core1(&core1_start);

    enum wifi_status wifi = init_wifi();
    if (wifi != wifi_status_connected) {
        watchdog_reboot(0, 0, 0);
    }

    init_webserver(&(struct sync_encre_file) {
        .acquire = &on_acquire_encre_file,
        .finish = &on_encre_file_finish,
    });

    return 0;
}
