cmake_minimum_required(VERSION 3.16)
project(vgate_core C)

# Portable C core: built on the laptop for replay checks and reused unchanged by
# the ESP32-S3 firmware (firmware/ adds this directory as an ESP-IDF component).
# Before the freeze only the classifier band-pass is ported and checked against
# Python (test_bandpass); the rest of the chain is ported after the freeze.

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_library(vgate_core STATIC
    src/biquad.c
)
target_include_directories(vgate_core PUBLIC include)

if(NOT MSVC)
    # No fused multiply-add: keeps float32 results bit-identical to the Python
    # reference (FMA alone shifts the band-pass by ~2e-4 mV).
    target_compile_options(vgate_core PRIVATE -Wall -Wextra -Wpedantic -ffp-contract=off)
    target_link_libraries(vgate_core PUBLIC m)
endif()

enable_testing()
add_executable(test_biquad tests/test_biquad.c)
target_link_libraries(test_biquad vgate_core)
add_test(NAME biquad COMMAND test_biquad)

add_executable(test_bandpass tests/test_bandpass.c)
target_include_directories(test_bandpass PRIVATE tests)
target_link_libraries(test_bandpass vgate_core)
add_test(NAME bandpass COMMAND test_bandpass)
