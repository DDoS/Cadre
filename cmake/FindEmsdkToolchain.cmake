include_guard()

set(emsdk_submodule "${CMAKE_CURRENT_LIST_DIR}/../external/emsdk")
set(emscripten_subpath "upstream/emscripten")
if(DEFINED ENV{EMSDK} AND NOT DEFINED ENV{CADRE_FORCE_LOCAL_EMSDK})
    message(STATUS "Using emsdk from \"$ENV{EMSDK}\"")
    set(emscripten_root "$ENV{EMSDK}/${emscripten_subpath}")
elseif(EXISTS "${emsdk_submodule}")
    set(emscripten_root "${emsdk_submodule}/${emscripten_subpath}")
    set(ENV{EMSDK} "${emsdk_submodule}")
else()
    message(FATAL_ERROR "Initialize the \"emsdk\" submodule, or use \"EMSDK\" to point to an external clone.")
endif()

set(emsdk_version 3.1.64)
message(STATUS "Setting up emsdk ${emsdk_version}")
if(CMAKE_HOST_WIN32)
    execute_process(COMMAND emsdk.bat install ${emsdk_version}
        WORKING_DIRECTORY "$ENV{EMSDK}"
        OUTPUT_QUIET ERROR_QUIET
        COMMAND_ERROR_IS_FATAL ANY)
    execute_process(COMMAND emsdk.bat activate ${emsdk_version}
        WORKING_DIRECTORY "$ENV{EMSDK}"
        OUTPUT_QUIET ERROR_QUIET
        COMMAND_ERROR_IS_FATAL ANY)
else()
    execute_process(COMMAND ./emsdk install ${emsdk_version}
        WORKING_DIRECTORY "$ENV{EMSDK}"
        OUTPUT_QUIET ERROR_QUIET
        COMMAND_ERROR_IS_FATAL ANY)
    execute_process(COMMAND ./emsdk activate ${emsdk_version}
        WORKING_DIRECTORY "$ENV{EMSDK}"
        OUTPUT_QUIET ERROR_QUIET
        COMMAND_ERROR_IS_FATAL ANY)
endif()

include("${emscripten_root}/cmake/Modules/Platform/Emscripten.cmake")

set(CMAKE_LINK_LIBRARY_USING_WHOLE_ARCHIVE
    "-Wl,--whole-archive" "<LINK_ITEM>" "-Wl,--no-whole-archive")
set(CMAKE_LINK_LIBRARY_USING_WHOLE_ARCHIVE_SUPPORTED ON)
