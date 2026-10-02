cmake_minimum_required(VERSION 3.16)
project(vgate_core C)

# Portable C core: built on the laptop for replay checks and reused unchanged by
# the ESP32-S3 firmware (firmware/ adds this directory as an ESP-IDF component).
# The port starts only after the freeze; until then this is a skeleton.

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_library(vgate_core STATIC
    src/biquad.c
)
target_include_directories(vgate_core PUBLIC include)

if(NOT MSVC)
    target_compile_options(vgate_core PRIVATE -Wall -Wextra -Wpedantic)
    target_link_libraries(vgate_core PUBLIC m)
endif()

enable_testing()
add_executable(test_biquad tests/test_biquad.c)
target_link_libraries(test_biquad vgate_core)
add_test(NAME biquad COMMAND test_biquad)
