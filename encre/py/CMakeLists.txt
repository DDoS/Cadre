find_package(Python 3 REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(py_encre "src/py_encre.cpp")

target_link_libraries(py_encre PRIVATE encre)

if(APPLE)
    target_link_options(py_encre PRIVATE "-Wl,-no_fixup_chains")
endif()
