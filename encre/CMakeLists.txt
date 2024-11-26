cmake_minimum_required(VERSION 3.23)
message(STATUS "Using toolchain file: ${CMAKE_TOOLCHAIN_FILE}")

project("encre" LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_EXTENSIONS OFF)

add_subdirectory(core)
add_subdirectory(cli)
add_subdirectory(py)
