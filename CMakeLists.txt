cmake_minimum_required(VERSION 3.8)

project(proxywrapper)

include(GNUInstallDirs)

set(CMAKE_MODULE_PATH ${CMAKE_CURRENT_LIST_DIR}/cmake)

find_package(libproxy REQUIRED)

add_library(${PROJECT_NAME} SHARED src/ProxyWrapper.cpp)
target_include_directories(${PROJECT_NAME}
    PUBLIC
        $<BUILD_INTERFACE:${proxywrapper_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include/${PROJECT_NAME}>
)
target_link_libraries(${PROJECT_NAME} PUBLIC PROXY::proxy)

install(TARGETS ${PROJECT_NAME} EXPORT proxywrapper DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(FILES include/ProxyWrapper.h DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/${PROJECT_NAME})
