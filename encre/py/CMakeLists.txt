find_package(Python 3 REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 CONFIG REQUIRED)

# Workaround for pybind11 package issue. See: https://github.com/microsoft/vcpkg/pull/36585
get_target_property(pybind11_definitions pybind11::pybind11_headers INTERFACE_COMPILE_DEFINITIONS)
list(FILTER pybind11_definitions EXCLUDE REGEX "Py_DEBUG")
set_property(TARGET pybind11::pybind11_headers PROPERTY INTERFACE_COMPILE_DEFINITIONS ${pybind11_definitions})

pybind11_add_module(py_encre "src/py_encre.cpp")

target_link_libraries(py_encre PRIVATE encre)

if(APPLE)
    target_link_options(py_encre PRIVATE "-Wl,-no_fixup_chains")
endif()
