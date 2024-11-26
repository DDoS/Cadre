include_guard()

if(DEFINED ENV{VCPKG_ROOT} AND NOT DEFINED ENV{CADRE_FORCE_LOCAL_VCPKG})
    message(STATUS "Using vcpkg from \"$ENV{VCPKG_ROOT}\"")
    include("$ENV{VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake")
elseif(EXISTS "${CMAKE_CURRENT_LIST_DIR}/../vcpkg")
    include("${CMAKE_CURRENT_LIST_DIR}/../vcpkg/scripts/buildsystems/vcpkg.cmake")
else()
    message(FATAL_ERROR "Initialize the \"vcpkg\" submodule, or use \"VCPKG_ROOT\" to point to an external clone.")
endif()
