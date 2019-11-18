set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86)

# NOTE: CMAKE_GENERATOR_PLATFORM does not support value of 'x86'.
# However, x86 is built by default when CMAKE_GENERATOR_PLATFORM is not set.
# Therefore, we omit setting CMAKE_GENERATOR_PLATFORM for x86 build.

set(CMAKE_C_COMPILER MSVC)
set(CMAKE_CXX_COMPILER MSVC)
