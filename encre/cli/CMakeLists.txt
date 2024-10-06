find_package(argparse QUIET CONFIG)
if(NOT argparse_FOUND)
    return()
endif()

add_executable(encre-cli)
target_sources(encre-cli PRIVATE
    "src/main.cpp"
)
target_link_libraries(encre-cli PRIVATE encre)
target_link_libraries(encre-cli PRIVATE argparse::argparse)
