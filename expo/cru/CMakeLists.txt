cmake_minimum_required(VERSION 3.23)

project("cru" LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Python 3 REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 CONFIG REQUIRED)

# Workaround for pybind11 package issue. See: https://github.com/microsoft/vcpkg/pull/36585
get_target_property(pybind11_definitions pybind11::pybind11_headers INTERFACE_COMPILE_DEFINITIONS)
list(FILTER pybind11_definitions EXCLUDE REGEX "Py_DEBUG")
set_property(TARGET pybind11::pybind11_headers PROPERTY INTERFACE_COMPILE_DEFINITIONS ${pybind11_definitions})

pybind11_add_module(cru "src/cru.cpp")

find_package(libraw CONFIG REQUIRED)
target_link_libraries(cru PRIVATE libraw::raw_r)

if(APPLE)
    target_link_options(cru PRIVATE "-Wl,-no_fixup_chains")
endif()
