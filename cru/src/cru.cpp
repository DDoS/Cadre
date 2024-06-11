#include "exif.hpp"

#include <libraw/libraw.h>

#include <vips/vips8>

#include <date/date.h>
#include <date/tz.h>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/chrono.h>

#include <optional>
#include <charconv>
#include <numeric>
#include <chrono>

namespace py = pybind11;

namespace {
    using local_milliseconds = date::local_time<std::chrono::milliseconds>;
    using sys_milliseconds = date::sys_time<std::chrono::milliseconds>;
    using frac_seconds = std::chrono::duration<double>;

    struct ImageInfo {
        uint32_t width{}, height{};

        struct Times {
            struct WithOffset {
                double seconds{};
                int64_t offset{};
            };
            std::optional<WithOffset> original;

            struct MaybeIncomplete {
                double seconds{};
                bool date_only{};
            };
            std::optional<MaybeIncomplete> gps;
        } times;

        struct MakeAndModel {
            std::optional<std::string> camera;
            std::optional<std::string> lens;
        } make_and_model;

        struct CameraSettings {
            std::optional<std::string> aperture;
            std::optional<std::string> exposure;
            std::optional<std::string> iso;
            std::optional<std::string> focal_length;
        } camera_settings;

        struct GPS {
            std::optional<double> longitude;
            std::optional<double> latitude;
            std::optional<double> altitude;
            std::optional<double> speed;
            std::optional<double> direction;
            enum class North {
                unknown,
                geographic,
                magnetic
            } zero_direction{};
        } gps;
    };

    double sys_milliseconds_to_timestamp(sys_milliseconds time) {
        return std::chrono::duration_cast<frac_seconds>(time.time_since_epoch()).count();
    }

    std::optional<ImageInfo::Times::WithOffset> get_exif_date_time(
            const std::optional<std::string_view>& maybe_date_str,
            const std::optional<std::string_view>& maybe_offset_str,
            const std::optional<std::string_view>& maybe_sub_seconds_str) {
        if (!maybe_date_str) {
            return std::nullopt;
        }

        std::string date_time_str{maybe_date_str->substr(0, 19)};
        std::string date_time_format{"%Y:%m:%d %H:%M:%S"};

        auto is_local_time = true;
        if (maybe_offset_str) {
            date_time_str += " ";
            date_time_str += maybe_offset_str->substr(0, 6);
            date_time_format += " %z";
            is_local_time = false;
        }

        sys_milliseconds capture_date;
        std::chrono::seconds offset;

        std::istringstream date_time_str_stream{date_time_str};
        if (is_local_time) {
            local_milliseconds capture_local_date;
            if (date::from_stream(date_time_str_stream, date_time_format.c_str(), capture_local_date)) {
                const auto local_time_zone = date::current_zone();
                capture_date = local_time_zone->to_sys(capture_local_date);
                offset = local_time_zone->get_info(capture_date).offset;
            }
        } else {
            std::string* abbreviation = nullptr;
            std::chrono::minutes offset_minutes;
            date::from_stream(date_time_str_stream, date_time_format.c_str(), capture_date, abbreviation, &offset_minutes);
            offset = std::chrono::duration_cast<std::chrono::seconds>(offset_minutes);
        }

        if (!date_time_str_stream) {
            return std::nullopt;
        }

        if (maybe_sub_seconds_str) {
            const auto sub_seconds_str = maybe_sub_seconds_str->substr(0, maybe_sub_seconds_str->find(' '));
            uint64_t sub_seconds{};
            if (std::from_chars(sub_seconds_str.begin(), sub_seconds_str.end(), sub_seconds).ec == std::errc{}) {
                capture_date += std::chrono::duration_cast<std::chrono::milliseconds>(
                    frac_seconds{sub_seconds * std::pow(10, -static_cast<int>(sub_seconds_str.length()))});
            }
        }

        return ImageInfo::Times::WithOffset{sys_milliseconds_to_timestamp(capture_date), offset.count()};
    }

    std::optional<std::string> get_exif_make_and_model(const std::optional<std::string_view>& make,
            const std::optional<std::string_view>& model) {
        if (!make && !model) {
            return std::nullopt;
        }

        if (make && model) {
            if (model->starts_with(*make)) {
                return std::string{*model};
            }

            return std::string{*make} + " " + std::string{*model};
        }

        return make ? std::string{*make} : std::string{*model};
    }

    template<typename... Args>
    std::optional<std::string> format_string(const char* format, Args&&... args) {
        std::array<char, 1024> buffer;
        if (const auto length = std::snprintf(buffer.data(), buffer.size(), format, std::forward<Args>(args)...);
                length >= 0) {
            return std::string{buffer.data(), std::min(static_cast<size_t>(length), buffer.size() - 1)};
        }

        return std::nullopt;
    }

    template<std::integral T>
    double rational_to_double(const Rational<T>& rational) {
        return static_cast<double>(rational.numerator) / rational.denominator;
    }

    template<std::integral T>
    std::optional<Rational<T>> normalize_rational(Rational<T> rational) {
        if (rational.denominator == 0) {
            return std::nullopt;
        }

        if constexpr (std::signed_integral<T>) {
            if (rational.denominator < 0) {
                rational.numerator = -rational.numerator;
                rational.denominator = -rational.denominator;
            }
        }

        const auto gcd = std::gcd(rational.numerator, rational.denominator);
        rational.numerator /= gcd;
        rational.denominator /= gcd;

        return Rational<T>{rational.numerator, rational.denominator};
    }

    template<std::integral T>
    std::optional<Rational<T>> normalize_rational(const std::optional<Rational<T>>& rational) {
        return rational ? normalize_rational(*rational) : std::nullopt;
    }

    template<std::integral T>
    std::tuple<T, Rational<T>> split_rational_whole_part(Rational<T> rational) {
        const auto whole_part = rational.numerator / rational.denominator;
        rational.numerator -= whole_part * rational.denominator;
        return {whole_part, {std::abs(rational.numerator), std::abs(rational.denominator)}};
    }

    ImageInfo::CameraSettings get_exif_camera_settings(const std::optional<Rational<uint32_t>>& f_number,
            const std::optional<Rational<uint32_t>>& exposure_time,
            const std::optional<Rational<int32_t>>& exposure_compensation,
            const std::optional<Rational<uint32_t>>& focal_length,
            std::optional<uint16_t> focal_length_35mm,
            const std::optional<uint32_t>& iso_speed,
            const std::optional<std::vector<uint16_t>>& iso_speed_ratings,
            uint32_t width, uint32_t height,
            const std::optional<Rational<uint32_t>>& focal_plane_x_resolution,
            const std::optional<Rational<uint32_t>>& focal_plane_y_resolution,
            const std::optional<uint16_t>& focal_plane_resolution_unit) {
        ImageInfo::CameraSettings settings{};

        if (const auto rational = normalize_rational(f_number)) {
            if (rational->numerator != 0) {
                settings.aperture = format_string("𝑓%.1f", rational_to_double(*rational));
            }
        }

        if (const auto rational = normalize_rational(exposure_time)) {
            if (rational->numerator != 0) {
                if (rational->numerator == 1) {
                    settings.exposure = format_string("%u/%u s", rational->numerator, rational->denominator);
                } else {
                    settings.exposure = format_string("%.1f s", rational_to_double(*rational));
                }
            }
        }

        if (const auto rational = normalize_rational(exposure_compensation)) {
            if (rational->numerator != 0) {
                if (!settings.exposure) {
                    settings.exposure = "? s";
                }

                *settings.exposure += ", ";

                if (rational->denominator == 1) {
                    *settings.exposure += format_string("%+d EV", rational->numerator).value_or("");
                } else {
                    const auto [whole, fraction] = split_rational_whole_part(*rational);
                    if (whole) {
                        *settings.exposure += format_string("%+d %d/%d EV", whole,
                                fraction.numerator, fraction.denominator).value_or("");
                    } else {
                        *settings.exposure += format_string("%+d/%d EV", fraction.numerator,
                                fraction.denominator).value_or("");
                    }
                }
            }
        }

        if (const auto rational = normalize_rational(focal_length)) {
            if (rational->numerator != 0) {
                const auto focal_length_value = rational_to_double(*rational);
                settings.focal_length = format_string("%d mm (native)", std::lround(focal_length_value));

                if ((!focal_length_35mm || focal_length_35mm == 0) &&
                        focal_plane_x_resolution && focal_plane_y_resolution &&
                        focal_plane_x_resolution->numerator != 0 && focal_plane_x_resolution->denominator != 0 &&
                        focal_plane_y_resolution->numerator != 0 && focal_plane_y_resolution->denominator != 0) {
                    auto sensor_width = width / rational_to_double(*focal_plane_x_resolution);
                    auto sensor_height = height / rational_to_double(*focal_plane_y_resolution);

                    double unit_scale{};
                    switch (focal_plane_resolution_unit.value_or(2))
                    {
                    case 2: // in
                        unit_scale = 25.4;
                        break;
                    case 3: // cm
                        unit_scale = 10;
                        break;
                    }
                    sensor_width *= unit_scale;
                    sensor_height *= unit_scale;

                    const auto sensor_diagonal = std::sqrt(sensor_width * sensor_width + sensor_height * sensor_height);
                    static const auto sensor_35mm_diagonal = std::sqrt(36 * 36 + 24 * 24);
                    const auto crop_factor_35mm = sensor_35mm_diagonal / sensor_diagonal;
                    if (std::abs(1 - crop_factor_35mm) >= 0.1) {
                        focal_length_35mm = static_cast<uint16_t>(std::lround(crop_factor_35mm * focal_length_value));
                    }
                }
            }
        }

        if (focal_length_35mm) {
            if (auto focal_length_35mm_str = format_string("%d mm (35mm film equivalent)", *focal_length_35mm)) {
                if (settings.focal_length) {
                    *settings.focal_length += ", " + *focal_length_35mm_str;
                } else {
                    settings.focal_length = std::move(focal_length_35mm_str);
                }
            }
        }

        if (iso_speed && iso_speed != 0) {
            settings.iso = format_string("ISO %u", *iso_speed);
        } else if (iso_speed_ratings && iso_speed_ratings->size() > 0) {
            settings.iso = format_string("ISO %u", iso_speed_ratings->at(0));
        }

        return settings;
    }

    double sexagesimal_to_decimal(const std::array<Rational<uint32_t>, 3>& sexagesimal) {
        return rational_to_double(sexagesimal[0]) +
                rational_to_double(sexagesimal[1]) / 60 +
                rational_to_double(sexagesimal[2]) / (60 * 60);
    }

    template<typename SourceDuration>
    frac_seconds double_duration_to_frac_seconds(double duration) {
        return std::chrono::duration_cast<frac_seconds>(
                std::chrono::duration<double, typename SourceDuration::period>{duration});
    }

    std::pair<ImageInfo::GPS, std::optional<ImageInfo::Times::MaybeIncomplete>> get_exif_gps(
            const std::optional<std::string_view>& gps_latitude_ref,
            const std::optional<std::array<Rational<uint32_t>, 3>>& gps_latitude,
            const std::optional<std::string_view>& gps_longitude_ref,
            const std::optional<std::array<Rational<uint32_t>, 3>>& gps_longitude,
            const std::optional<uint8_t>& gps_altitude_ref,
            const std::optional<Rational<uint32_t>>& gps_altitude,
            const std::optional<std::string_view>& gps_speed_ref,
            const std::optional<Rational<uint32_t>>& gps_speed,
            const std::optional<std::string_view>& gps_img_direction_ref,
            const std::optional<Rational<uint32_t>>& gps_img_direction,
            const std::optional<std::string_view>& gps_date_stamp,
            const std::optional<std::array<Rational<uint32_t>, 3>>& gps_time_stamp) {
        ImageInfo::GPS gps{};

        if (gps_latitude_ref && gps_latitude) {
            gps.latitude = sexagesimal_to_decimal(*gps_latitude);
            if (gps_latitude_ref == "S") {
                gps.latitude = -*gps.latitude;
            }
        }

        if (gps_longitude_ref && gps_longitude) {
            gps.longitude = sexagesimal_to_decimal(*gps_longitude);
            if (gps_longitude_ref == "W") {
                gps.longitude = -*gps.longitude;
            }
        }

        if (gps_altitude_ref && gps_altitude) {
            gps.altitude = rational_to_double(*gps_altitude);
            if (gps_altitude_ref == 1) {
                gps.altitude = -*gps.altitude;
            }
        }

        if (gps_speed_ref && gps_speed) {
            gps.speed = rational_to_double(*gps_speed);
            if (gps_speed_ref == "M") {
                gps.speed = 1.609344 * *gps.speed;
            } else if (gps_speed_ref == "N") {
                gps.speed = 1.852 * *gps.speed;
            }
        }

        if (gps_img_direction) {
            gps.direction = rational_to_double(*gps_img_direction);
            if (gps_img_direction_ref == "T") {
                gps.zero_direction = ImageInfo::GPS::North::geographic;
            } else if (gps_img_direction_ref == "M") {
                gps.zero_direction = ImageInfo::GPS::North::magnetic;
            }
        }

        std::optional<ImageInfo::Times::MaybeIncomplete> gps_date_time{};
        if (gps_date_stamp) {
            date::sys_time<frac_seconds> gps_date;
            std::istringstream date_time_str_stream{std::string{gps_date_stamp->substr(0, 10)}};
            if (date::from_stream(date_time_str_stream, "%Y:%m:%d", gps_date)) {
                gps_date_time.emplace();
                if (gps_time_stamp) {
                    gps_date += double_duration_to_frac_seconds<std::chrono::hours>(rational_to_double(gps_time_stamp->at(0)));
                    gps_date += double_duration_to_frac_seconds<std::chrono::minutes>(rational_to_double(gps_time_stamp->at(1)));
                    gps_date += double_duration_to_frac_seconds<std::chrono::seconds>(rational_to_double(gps_time_stamp->at(2)));
                } else {
                    gps_date_time->date_only = true;
                }

                gps_date_time->seconds = gps_date.time_since_epoch().count();
            }
        }

        return {gps, gps_date_time};
    }

    std::optional<ImageInfo> load_raw_image_info(const char* path) {
        LibRaw raw_processor;

        ExifData exif;
        raw_processor.set_exifparser_handler(ExifData::parser_callback, &exif);

        const auto result = raw_processor.open_file(path);
        switch (result) {
            case LIBRAW_SUCCESS:
                break;
            case LIBRAW_FILE_UNSUPPORTED:
            case LIBRAW_NOT_IMPLEMENTED:
                return std::nullopt;
            default:
                throw std::runtime_error{"Error reading raw image (code " + std::to_string(result) + ")"};
        }

        // Raw image size isn't the final processed image size
        // (in fact it's a bit bigger), but aspect ratio is what matters.
        // Flip bits 1 and 2 only mirror horizontally and vertically.
        // This has no effect on the image size.

        const auto& data = raw_processor.imgdata;
        auto width = data.sizes.width;
        auto height = data.sizes.height;
        if (data.sizes.flip & 4) {
            std::swap(width, height);
        }

        ImageInfo info{.width = width, .height = height};

        info.times.original = get_exif_date_time(exif.date_time_original,
                exif.offset_time_original, exif.sub_sec_time_original);
        info.make_and_model.camera = get_exif_make_and_model(exif.make, exif.model);
        info.make_and_model.lens = get_exif_make_and_model(exif.lens_make, exif.lens_model);
        info.camera_settings = get_exif_camera_settings(exif.f_number, exif.exposure_time, exif.exposure_compensation,
                exif.focal_length, exif.focal_length_35mm, exif.iso_speed, exif.iso_speed_ratings,
                width, height, exif.focal_plane_x_resolution, exif.focal_plane_y_resolution, exif.focal_plane_resolution_unit);
        std::tie(info.gps, info.times.gps) = get_exif_gps(exif.gps_latitude_ref, exif.gps_latitude, exif.gps_longitude_ref,
                exif.gps_longitude, exif.gps_altitude_ref, exif.gps_altitude, exif.gps_speed_ref,
                exif.gps_speed, exif.gps_img_direction_ref, exif.gps_img_direction, exif.gps_date_stamp,
                exif.gps_time_stamp);

        if (!info.times.original && data.other.timestamp > 0) {
            const auto capture_date = sys_milliseconds{std::chrono::seconds(data.other.timestamp)};;
            const auto local_time_zone = date::current_zone();
            info.times.original = ImageInfo::Times::WithOffset{sys_milliseconds_to_timestamp(capture_date),
                    local_time_zone->get_info(capture_date).offset.count()};
        }

        return info;
    }

    std::optional<std::string_view> try_get_raw_field(const vips::VImage& image, const char* name) {
        try {
            return image.get_string(name);
        } catch (const vips::VError&) {
            return std::nullopt;
        }
    }

    std::optional<std::string_view> try_get_string_field(const vips::VImage& image, const char* name) {
        const auto maybe_string = try_get_raw_field(image, name);
        if (!maybe_string) {
            return std::nullopt;
        }

        auto string = *maybe_string;

        // Format: "<value> (<value>, ASCII, N components, B bytes)",
        static constexpr std::string_view tag_info_separator{", "};
        for (size_t i = 0; i < 3; i++) {
            const auto separator_pos = string.rfind(tag_info_separator);
            if (separator_pos == std::string::npos) {
                return std::nullopt;
            }

            string = string.substr(0, separator_pos);
        }

        // string should be now "<value> (<value>",  so split it halfway
        // Hopefully we get better EXIF data soon enough: https://github.com/libvips/libvips/issues/4002
        return string.substr(0, string.size() / 2 - 1);
    }

    static constexpr size_t any_count = std::numeric_limits<size_t>::max();

    template<typename Element, size_t count>
    struct GetFieldReturnTraits {
        using Collection = std::conditional_t<count == any_count, std::vector<Element>, std::array<Element, count>>;
        static constexpr auto many = count != 1;
        using Return = std::optional<std::conditional_t<many, Collection, Element>>;
    };

    template<std::integral Number, size_t count = 1>
    auto try_get_integer_field(const vips::VImage& image, const char* name) {
        using Traits = GetFieldReturnTraits<Number, count>;

        const auto maybe_string = try_get_raw_field(image, name);
        if (!maybe_string) {
            return typename Traits::Return{};
        }

        auto string = *maybe_string;

        // Format: "<value> [...] (<pretty value>, Long, N components, B bytes)"

        typename Traits::Collection integers{};
        for (size_t i = 0; i < count; i++) {
            Number integer{};
            if (const auto [ptr, ec] = std::from_chars(string.begin(), string.end(), integer); ec == std::errc{}) {
                string = string.substr(ptr - string.begin());
            } else {
                return typename Traits::Return{};
            }

            if constexpr (count == any_count) {
                integers.push_back(integer);
            } else {
                integers[i] = integer;
            }

            string = string.substr(1); // ' '
            if (string.front() == '(') {
                break;
            }
        }

        if constexpr (Traits::many) {
            return typename Traits::Return{std::move(integers)};
        } else {
            return typename Traits::Return{integers[0]};
        }
    }

    template<size_t count = 1, bool signed_ = false>
    auto try_get_rational_field(const vips::VImage& image, const char* name) {
        using Number = std::conditional_t<signed_, int32_t, uint32_t>;
        using RationalT = Rational<Number>;
        using Traits = GetFieldReturnTraits<RationalT, count>;

        const auto maybe_string = try_get_raw_field(image, name);
        if (!maybe_string) {
            return typename Traits::Return{};
        }

        auto string = *maybe_string;

        // Format: "<numerator>/<denominator> [...] (<pretty value>, Rational, N components, B bytes)"

        typename Traits::Collection rationals{};
        for (size_t i = 0; i < count; i++) {
            Number numerator{};
            if (const auto [ptr, ec] = std::from_chars(string.begin(), string.end(), numerator); ec == std::errc{}) {
                string = string.substr(ptr - string.begin());
            } else {
                return typename Traits::Return{};
            }

            string = string.substr(1); // '/'

            Number denominator{};
            if (const auto [ptr, ec] = std::from_chars(string.begin(), string.end(), denominator); ec == std::errc{}) {
                string = string.substr(ptr - string.begin());
            } else {
                return typename Traits::Return{};
            }

            const RationalT rational{numerator, denominator};
            if constexpr (count == any_count) {
                rationals.push_back(rational);
            } else {
                rationals[i] = rational;
            }

            string = string.substr(1); // ' '
            if (string.front() == '(') {
                break;
            }
        }

        if constexpr (Traits::many) {
            return typename Traits::Return{std::move(rationals)};
        } else {
            return typename Traits::Return{rationals[0]};
        }
    }

    std::optional<ImageInfo> load_vips_image_info(const char* path) {
        vips::VImage image;
        try {
            image = vips::VImage::new_from_file(path);
        } catch (const std::exception&) {
            return std::nullopt;
        }

        const auto width = static_cast<uint32_t>(image.width());
        const auto height = static_cast<uint32_t>(image.height());
        ImageInfo info{.width = width, .height = height};

        info.times.original = get_exif_date_time(
                try_get_string_field(image, "exif-ifd2-DateTimeOriginal"),
                try_get_string_field(image, "exif-ifd2-OffsetTimeOriginal"),
                try_get_string_field(image, "exif-ifd2-SubSecTimeOriginal"));
        info.make_and_model.camera = get_exif_make_and_model(
                try_get_string_field(image, "exif-ifd0-Make"),
                try_get_string_field(image, "exif-ifd0-Model"));
        info.make_and_model.lens = get_exif_make_and_model(
                try_get_string_field(image, "exif-ifd2-LensMake"),
                try_get_string_field(image, "exif-ifd2-LensModel"));
        info.camera_settings = get_exif_camera_settings(
                try_get_rational_field(image, "exif-ifd2-FNumber"),
                try_get_rational_field(image, "exif-ifd2-ExposureTime"),
                try_get_rational_field<1, true>(image, "exif-ifd2-ExposureBiasValue"),
                try_get_rational_field(image, "exif-ifd2-FocalLength"),
                try_get_integer_field<uint16_t>(image, "exif-ifd2-FocalLengthIn35mmFilm"),
                try_get_integer_field<uint32_t>(image, "exif-ifd2-ISO Speed"),
                try_get_integer_field<uint16_t, any_count>(image, "exif-ifd2-ISOSpeedRatings"),
                width, height,
                try_get_rational_field(image, "exif-ifd2-FocalPlaneXResolution"),
                try_get_rational_field(image, "exif-ifd2-FocalPlaneYResolution"),
                try_get_integer_field<uint16_t>(image, "exif-ifd2-FocalPlaneResolutionUnit"));

        // libvips returns byte fields as formatted strings instead of numbers for some reason.
        // Bug? https://github.com/libvips/libvips/issues/4002
        std::optional<uint8_t> altitude_ref;
        if (const auto altitude_ref_str = try_get_raw_field(image, "exif-ifd3-GPSAltitudeRef")) {
            altitude_ref = altitude_ref_str->starts_with("Below Sea Level");
        }

        std::tie(info.gps, info.times.gps) = get_exif_gps(
                try_get_string_field(image, "exif-ifd3-GPSLatitudeRef"),
                try_get_rational_field<3>(image, "exif-ifd3-GPSLatitude"),
                try_get_string_field(image, "exif-ifd3-GPSLongitudeRef"),
                try_get_rational_field<3>(image, "exif-ifd3-GPSLongitude"),
                altitude_ref, // try_get_integer_field<uint8_t>(image, "exif-ifd3-GPSAltitudeRef"),
                try_get_rational_field(image, "exif-ifd3-GPSAltitude"),
                try_get_string_field(image, "exif-ifd3-GPSSpeedRef"),
                try_get_rational_field(image, "exif-ifd3-GPSSpeed"),
                try_get_string_field(image, "exif-ifd3-GPSImgDirectionRef"),
                try_get_rational_field(image, "exif-ifd3-GPSImgDirection"),
                try_get_string_field(image, "exif-ifd3-GPSDateStamp"),
                try_get_rational_field<3>(image, "exif-ifd3-GPSTimeStamp"));

        return info;
    }

    std::optional<ImageInfo> load_image_info(const char* path) {
        if (const auto raw_info = load_raw_image_info(path)) {
            return raw_info;
        }

        return load_vips_image_info(path);
    }
}

PYBIND11_MODULE(cru, m) {
    m.doc() = "Python bindings for Cru";

    py::class_<ImageInfo::Times::WithOffset>(m, "TimeWithOffset").
        def_readonly("seconds", &ImageInfo::Times::WithOffset::seconds).
        def_readonly("offset", &ImageInfo::Times::WithOffset::offset);

    py::class_<ImageInfo::Times::MaybeIncomplete>(m, "MaybeIncomplete").
        def_readonly("seconds", &ImageInfo::Times::MaybeIncomplete::seconds).
        def_readonly("date_only", &ImageInfo::Times::MaybeIncomplete::date_only);

    py::class_<ImageInfo::Times>(m, "Times").
        def_readonly("original", &ImageInfo::Times::original).
        def_readonly("gps", &ImageInfo::Times::gps);

    py::class_<ImageInfo::MakeAndModel>(m, "MakeAndModel").
        def_readonly("camera", &ImageInfo::MakeAndModel::camera).
        def_readonly("lens", &ImageInfo::MakeAndModel::lens);

    py::class_<ImageInfo::CameraSettings>(m, "CameraSettings").
        def_readonly("aperture", &ImageInfo::CameraSettings::aperture).
        def_readonly("exposure", &ImageInfo::CameraSettings::exposure).
        def_readonly("iso", &ImageInfo::CameraSettings::iso).
        def_readonly("focal_length", &ImageInfo::CameraSettings::focal_length);

    py::enum_<ImageInfo::GPS::North>(m, "GpsNorth").
        value("unknown", ImageInfo::GPS::North::unknown).
        value("geographic", ImageInfo::GPS::North::geographic).
        value("magnetic", ImageInfo::GPS::North::magnetic);

    py::class_<ImageInfo::GPS>(m, "GPS").
        def_readonly("longitude", &ImageInfo::GPS::longitude).
        def_readonly("latitude", &ImageInfo::GPS::latitude).
        def_readonly("altitude", &ImageInfo::GPS::altitude).
        def_readonly("direction", &ImageInfo::GPS::direction).
        def_readonly("speed", &ImageInfo::GPS::speed).
        def_readonly("zero_direction", &ImageInfo::GPS::zero_direction);

    py::class_<ImageInfo>(m, "ImageInfo").
        def_readonly("width", &ImageInfo::width).
        def_readonly("height", &ImageInfo::height).
        def_readonly("times", &ImageInfo::times).
        def_readonly("make_and_model", &ImageInfo::make_and_model).
        def_readonly("camera_settings", &ImageInfo::camera_settings).
        def_readonly("gps", &ImageInfo::gps);

    m.def("load_image_info", &load_image_info, py::arg("path"), "Load raw image info");

    setenv("VIPS_WARNING", "1", true);
    if (VIPS_INIT("")) {
        vips_error_exit(nullptr);
    }
}
