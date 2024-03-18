add_executable(encre-cli)

target_sources(encre-cli PRIVATE
    "src/main.cpp"
)

target_link_libraries(encre-cli PRIVATE encre)

find_package(argparse CONFIG REQUIRED)
target_link_libraries(encre-cli PRIVATE argparse::argparse)
