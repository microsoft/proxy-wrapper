
cmake_minimum_required(VERSION 3.8)

project(proxywrapper)

include(GNUInstallDirs)

find_library(proxy REQUIRED)

add_library(proxywrapper SHARED proxywrapper.cpp)

target_link_libraries(proxywrapper proxy)
