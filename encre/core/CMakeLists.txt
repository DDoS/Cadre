set(export_header_path "${CMAKE_CURRENT_SOURCE_DIR}/include/encre_export.hpp")
if(EMSCRIPTEN)
    add_library(encre STATIC)

    set(em_options
        "-pthread"
        "-fexceptions"
        "-msimd128")
    target_compile_options(encre PUBLIC ${em_options})
    target_link_options(encre PUBLIC ${em_options} -sWASM_BIGINT)
    target_compile_definitions(encre PUBLIC WASM_SIMD_COMPAT_SLOW)

    file(WRITE "${export_header_path}" [=[
#pragma once
#define ENCRE_EXPORT
]=])
else()
    add_library(encre SHARED)

    include(GenerateExportHeader)
    generate_export_header(encre EXPORT_FILE_NAME "${export_header_path}")
endif()

set_target_properties(encre PROPERTIES
    INTERPROCEDURAL_OPTIMIZATION ON
    INTERPROCEDURAL_OPTIMIZATION_DEBUG OFF
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON)

target_include_directories(encre PUBLIC "include")
target_sources(encre PRIVATE
    "include/encre.hpp"
    "${export_header_path}"
    "src/lightness.hpp"
    "src/lightness.cpp"
    "src/dither.hpp"
    "src/dither.cpp"
    "src/encre.cpp"
    "src/oklab.hpp"
    "src/oklab.cpp"
    "src/palette.cpp"
)

find_package(glm CONFIG REQUIRED)
target_link_libraries(encre PUBLIC glm::glm)

find_package(Qhull CONFIG REQUIRED)
target_link_libraries(encre PRIVATE Qhull::qhull_r Qhull::qhullcpp)

find_package(PkgConfig REQUIRED)
pkg_search_module(vips REQUIRED IMPORTED_TARGET "vips-cpp")
if(EMSCRIPTEN)
    # Remove libc++ from pkg-config, because it conflicts with multithreaded
    # libc++ from emscripten
    get_target_property(vips_libraries PkgConfig::vips INTERFACE_LINK_LIBRARIES)
    list(FILTER vips_libraries EXCLUDE REGEX [[libc\+\+]])
    set_target_properties(PkgConfig::vips PROPERTIES
        INTERFACE_LINK_LIBRARIES "${vips_libraries}")
    # Add missing library directory
    target_link_directories(PkgConfig::vips INTERFACE ${vips_LIBRARY_DIRS})
endif()
target_link_libraries(encre PRIVATE PkgConfig::vips)
