# ESP32-S3 replay firmware: runs the portable C core (../c) on MIT-BIH samples
# streamed over the native USB port and prints the same lines as c/tools/vgate_replay.
cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(vgate_replay)
