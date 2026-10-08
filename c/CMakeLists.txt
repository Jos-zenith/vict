cmake_minimum_required(VERSION 3.16)
project(vgate_core C)

# Portable C core: built on the laptop for replay checks and reused unchanged by
# the ESP32-S3 firmware (firmware/ adds this directory's sources as an ESP-IDF
# component). Every stage is checked against the Python reference:
# tests/ against committed golden vectors, scripts/check_c_core.py on whole records.

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_library(vgate_core STATIC
    src/biquad.c
    src/features.c
    src/numeric.c
    src/pan_tompkins.c
    src/params.c
    src/pipeline.c
    src/svm.c
)
target_include_directories(vgate_core PUBLIC include)

if(MSVC)
    # /fp:precise (the default) never contracts to FMA on x64.
    target_compile_options(vgate_core PRIVATE /W4 /fp:precise)
else()
    # No fused multiply-add: keeps results bit-identical to the Python reference
    # (FMA alone shifts the band-pass by ~2e-4 mV).
    target_compile_options(vgate_core PRIVATE -Wall -Wextra -Wpedantic -ffp-contract=off)
    target_link_libraries(vgate_core PUBLIC m)
endif()

add_executable(vgate_replay tools/vgate_replay.c)
target_link_libraries(vgate_replay vgate_core)

enable_testing()
add_executable(test_biquad tests/test_biquad.c)
target_link_libraries(test_biquad vgate_core)
add_test(NAME biquad COMMAND test_biquad)

add_executable(test_bandpass tests/test_bandpass.c)
target_include_directories(test_bandpass PRIVATE tests)
target_link_libraries(test_bandpass vgate_core)
add_test(NAME bandpass COMMAND test_bandpass)

add_executable(test_pipeline tests/test_pipeline.c)
target_include_directories(test_pipeline PRIVATE tests)
target_link_libraries(test_pipeline vgate_core)
add_test(NAME pipeline COMMAND test_pipeline)
