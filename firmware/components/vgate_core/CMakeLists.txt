# The laptop C core, unchanged: same sources as c/CMakeLists.txt.
set(core "${CMAKE_CURRENT_LIST_DIR}/../../../c")
file(GLOB srcs "${core}/src/*.c")
idf_component_register(SRCS ${srcs} INCLUDE_DIRS "${core}/include")
# The S3 FPU has a fused multiply-add (madd.s); contracting a*b + c into it would
# change the float32 band-pass. Doubles are IEEE soft-float (libgcc), correctly rounded.
target_compile_options(${COMPONENT_LIB} PRIVATE -ffp-contract=off)
