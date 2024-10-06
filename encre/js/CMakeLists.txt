add_executable(js_encre)

target_compile_definitions(js_encre PRIVATE WASM_SIMD_COMPAT_SLOW)
target_link_options(js_encre PRIVATE --bind -sALLOW_MEMORY_GROWTH=1)
target_sources(js_encre PRIVATE "src/js_encre.cpp")
target_link_libraries(js_encre PRIVATE encre)
