cmake_minimum_required(VERSION 3.23)

project("encre" LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_EXTENSIONS OFF)

add_subdirectory(core)
add_subdirectory(cli)
add_subdirectory(py)
