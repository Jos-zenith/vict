idf_component_register(SRCS "replay_main.c"
                       PRIV_REQUIRES vgate_core driver esp_hw_support)
target_compile_options(${COMPONENT_LIB} PRIVATE -ffp-contract=off)
