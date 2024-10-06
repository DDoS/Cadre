include_guard()

set(emscripten_subpath "upstream/emscripten")
if(DEFINED ENV{EMSDK} AND NOT DEFINED ENV{CADRE_FORCE_LOCAL_EMSDK})
    message(STATUS "Using emsdk from \"$ENV{EMSDK}\"")
    set(emscripten_root "$ENV{EMSDK}/${emscripten_subpath}")
elseif(EXISTS "${CMAKE_CURRENT_LIST_DIR}/../emsdk")
    set(emscripten_root "${CMAKE_CURRENT_LIST_DIR}/../emsdk/${emscripten_subpath}")
    set(ENV{EMSDK} "${CMAKE_CURRENT_LIST_DIR}/../emsdk")
else()
    message(FATAL_ERROR "Initialize the \"emsdk\" submodule, or use \"EMSDK\" to point to an external clone.")
endif()

message(STATUS "Setting up emsdk")
if(CMAKE_HOST_WIN32)
    execute_process(COMMAND emsdk.bat install latest
        WORKING_DIRECTORY "$ENV{EMSDK}"
        OUTPUT_QUIET ERROR_QUIET
        COMMAND_ERROR_IS_FATAL ANY)
    execute_process(COMMAND emsdk.bat activate latest
        WORKING_DIRECTORY "$ENV{EMSDK}"
        OUTPUT_QUIET ERROR_QUIET
        COMMAND_ERROR_IS_FATAL ANY)
else()
    execute_process(COMMAND ./emsdk install latest
        WORKING_DIRECTORY "$ENV{EMSDK}"
        OUTPUT_QUIET ERROR_QUIET
        COMMAND_ERROR_IS_FATAL ANY)
    execute_process(COMMAND ./emsdk activate latest
        WORKING_DIRECTORY "$ENV{EMSDK}"
        OUTPUT_QUIET ERROR_QUIET
        COMMAND_ERROR_IS_FATAL ANY)
endif()

include("${emscripten_root}/cmake/Modules/Platform/Emscripten.cmake")
