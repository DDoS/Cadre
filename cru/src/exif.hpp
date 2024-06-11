#pragma once

#include <libraw/libraw_types.h>

#include <array>
#include <vector>
#include <string>
#include <concepts>
#include <optional>

template<std::integral T>
struct Rational {
    T numerator;
    T denominator;

    operator std::string() const {
        return std::to_string(numerator) + "/" + std::to_string(denominator);
    }
};

struct ExifData {
    std::optional<std::string> make; // 0x010f
    std::optional<std::string> model; // 0x0110

    std::optional<std::string> lens_make; // 0xa433
    std::optional<std::string> lens_model; // 0xa434

    std::optional<Rational<uint32_t>> focal_plane_x_resolution; // 0xa20e
    std::optional<Rational<uint32_t>> focal_plane_y_resolution; // 0xa20f
    std::optional<uint16_t> focal_plane_resolution_unit; // 0xa210

    std::optional<Rational<uint32_t>> f_number{}; // 0x829d
    std::optional<Rational<uint32_t>> exposure_time{}; // 0x829a
    std::optional<Rational<int32_t>> exposure_compensation{}; // 0x9204
    std::optional<Rational<uint32_t>> focal_length{}; // 0x920a
    std::optional<uint16_t> focal_length_35mm{}; // 0xa405
    std::optional<uint32_t> iso_speed{}; // 0x8833
    std::optional<std::vector<uint16_t>> iso_speed_ratings{}; // 0x8827

    std::optional<std::string> date_time_original; // 0x9003
    std::optional<std::string> offset_time_original; // 0x9011
    std::optional<std::string> sub_sec_time_original; // 0x9291

    std::optional<std::string> gps_latitude_ref; // 0x0001
    std::optional<std::array<Rational<uint32_t>, 3>> gps_latitude{}; // 0x0002
    std::optional<std::string> gps_longitude_ref; // 0x0003
    std::optional<std::array<Rational<uint32_t>, 3>> gps_longitude{}; // 0x0004
    std::optional<uint8_t> gps_altitude_ref; // 0x0005
    std::optional<Rational<uint32_t>> gps_altitude{}; // 0x0006
    std::optional<std::string> gps_speed_ref; // 0x000c
    std::optional<Rational<uint32_t>> gps_speed{}; // 0x000d
    std::optional<std::string> gps_img_direction_ref; // 0x0010
    std::optional<Rational<uint32_t>> gps_img_direction; // 0x0011
    std::optional<std::string> gps_date_stamp; // 0x001d
    std::optional<std::array<Rational<uint32_t>, 3>> gps_time_stamp{}; // 0x0007

    static void parser_callback(void *context, int tag, int type, int count,
            unsigned int order, void* file, INT64 base);
};
