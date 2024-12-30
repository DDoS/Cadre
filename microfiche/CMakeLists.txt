cmake_minimum_required(VERSION 3.23)
cmake_policy(SET CMP0169 OLD)

include(FetchContent)
FetchContent_Declare(pico-sdk
  GIT_REPOSITORY https://github.com/raspberrypi/pico-sdk.git
  GIT_TAG 2.1.1
  GIT_SHALLOW
  GIT_REMOTE_UPDATE_STRATEGY CHECKOUT
)
FetchContent_Populate(pico-sdk)

include("${pico-sdk_SOURCE_DIR}/pico_sdk_init.cmake")
project(microfiche LANGUAGES C CXX)

set(CMAKE_C_STANDARD 17)
set(CMAKE_CXX_STANDARD 23)

pico_sdk_init()

FetchContent_Declare(picow_http
  GIT_REPOSITORY https://gitlab.com/DDoSQc/picow_http.git
  GIT_TAG longer-content
  GIT_SHALLOW
  GIT_REMOTE_UPDATE_STRATEGY CHECKOUT
)
FetchContent_MakeAvailable(picow_http)

add_library(lwipopts INTERFACE)
target_sources(lwipopts INTERFACE
    "${picow_http_SOURCE_DIR}/etc/lwipopts.h")
target_include_directories(lwipopts INTERFACE
    "${picow_http_SOURCE_DIR}/etc")

add_executable(microfiche)
target_sources(microfiche PRIVATE
    "include/lwipopts.h"
    "src/cors.h"
    "src/cors.c"
    "src/cors_preflight_handler.h"
    "src/cors_preflight_handler.c"
    "src/encre_file.h"
    "src/encre_file.c"
    "src/GDEP073E01.h"
    "src/GDEP073E01.c"
    "src/image_handler.h"
    "src/image_handler.c"
    "src/main.c"
    "src/webserver.h"
    "src/webserver.c"
    "src/wifi.h"
    "src/wifi.c")
target_include_directories(microfiche PRIVATE "include")
target_compile_definitions(microfiche PRIVATE
    PICOW_HTTPS=0)
target_link_libraries(microfiche PRIVATE
    hardware_spi
    hardware_flash
    hardware_watchdog
    pico_unique_id
    pico_multicore
    pico_stdio
    pico_stdlib
    pico_flash
    pico_lwip
    pico_lwip_arch
    pico_lwip_mdns
    pico_cyw43_arch_lwip_poll
    lwipopts
    picow_http)

set(web_data_dir "${CMAKE_SOURCE_DIR}/www")
picow_http_gen_handlers(microfiche
    "${web_data_dir}/www.yaml"
    "${web_data_dir}"
    "${web_data_dir}/index.html")

pico_enable_stdio_usb(microfiche ON)
pico_enable_stdio_uart(microfiche ON)

pico_add_extra_outputs(microfiche)

pico_set_program_description(microfiche "Affiche for the Raspberry Pi Pico 2 W")
pico_set_program_url(microfiche "https://github.com/DDoS/Cadre")

include("../cmake/PicoDebugProbe.cmake")
picoprobe_add_flash_target(microfiche)
picoprobe_add_reset_target(microfiche)
