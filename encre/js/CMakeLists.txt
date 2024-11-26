add_executable(js_encre)

target_sources(js_encre PRIVATE "src/js_encre.cpp")
target_link_libraries(js_encre PRIVATE $<LINK_LIBRARY:WHOLE_ARCHIVE,encre>)

set(test_data_dir "${CMAKE_CURRENT_LIST_DIR}/../test_data")
cmake_path(NORMAL_PATH test_data_dir)
target_link_options(js_encre PRIVATE "--preload-file=${test_data_dir}@/")

# Based on:
# https://github.com/kleisauke/wasm-vips/blob/v0.0.10/src/CMakeLists.txt#L117
target_link_options(js_encre PRIVATE
    -sSAFE_HEAP=1
    -sASSERTIONS=2
    --bind
    -sENVIRONMENT=web,worker
    -sALLOW_MEMORY_GROWTH=1
    -sABORTING_MALLOC=0
    -sMALLOC=mimalloc
    -sSTACK_SIZE=256KB
    -sALLOW_TABLE_GROWTH
    -sTEXTDECODER=2
    -sFORCE_FILESYSTEM
    -sEXCEPTION_STACK_TRACES
    -sPTHREAD_POOL_SIZE='Math.max\(navigator.hardwareConcurrency,6\)')
