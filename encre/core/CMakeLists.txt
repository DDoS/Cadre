include(GenerateExportHeader)

add_library(encre SHARED)

set_target_properties(encre PROPERTIES
    INTERPROCEDURAL_OPTIMIZATION ON
    INTERPROCEDURAL_OPTIMIZATION_DEBUG OFF
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON)
set(export_header_path "${CMAKE_CURRENT_SOURCE_DIR}/include/encre_export.hpp")

target_include_directories(encre PUBLIC "include")
target_sources(encre PRIVATE
    "include/encre.hpp"
    "${export_header_path}"
    "src/contrast.cpp"
    "src/contrast.hpp"
    "src/dither.hpp"
    "src/dither.cpp"
    "src/encre.cpp"
    "src/oklab.hpp"
    "src/oklab.cpp"
)
generate_export_header(encre EXPORT_FILE_NAME "${export_header_path}")

find_package(glm CONFIG REQUIRED)
target_link_libraries(encre PUBLIC glm::glm)

find_package(Qhull CONFIG REQUIRED)
target_link_libraries(encre PRIVATE Qhull::qhull_r Qhull::qhullcpp)

find_package(PkgConfig REQUIRED)
pkg_search_module(vips REQUIRED IMPORTED_TARGET "vips-cpp")
target_link_libraries(encre PRIVATE PkgConfig::vips)
