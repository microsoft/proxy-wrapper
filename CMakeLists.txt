cmake_minimum_required(VERSION 3.8)

project(proxywrapper)

include(GNUInstallDirs)

find_library(proxy REQUIRED)

set(PROXYWRAP_LIB_NAME ${PROJECT_NAME})
add_library(${PROXYWRAP_LIB_NAME} SHARED src/ProxyWrapper.cpp)
target_include_directories(${PROXYWRAP_LIB_NAME}
    PUBLIC
        $<BUILD_INTERFACE:${proxywrapper_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include/${PROXYWRAP_LIB_NAME}>
)
target_link_libraries(${PROXYWRAP_LIB_NAME} PUBLIC proxy)

install(TARGETS ${PROXYWRAP_LIB_NAME} EXPORT proxywrapper DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(FILES include/ProxyWrapper.h DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/${PROXYWRAP_LIB_NAME})
