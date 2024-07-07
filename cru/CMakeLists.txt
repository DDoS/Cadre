cmake_minimum_required(VERSION 3.23)

project("cru" LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Python 3 REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(cru
    "src/cru.cpp"
    "src/exif.hpp"
    "src/exif.cpp")

find_package(libraw CONFIG REQUIRED)
target_link_libraries(cru PRIVATE libraw::raw_r)

find_package(PkgConfig REQUIRED)
pkg_search_module(vips REQUIRED IMPORTED_TARGET "vips-cpp")
target_link_libraries(cru PRIVATE PkgConfig::vips)

find_package(date CONFIG REQUIRED)
target_link_libraries(cru PRIVATE date::date date::date-tz)

if(APPLE)
    target_link_options(cru PRIVATE "-Wl,-no_fixup_chains")
endif()
