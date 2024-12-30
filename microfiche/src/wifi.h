#pragma once

enum wifi_status {
    wifi_status_connected,
    wifi_status_connection_failed,
    wifi_status_no_network,
};

enum wifi_status init_wifi();
