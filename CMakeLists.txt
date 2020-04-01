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
target_link_libraries(${PROJECT_NAME} PUBLIC libproxy::proxy)

# Install the lib while also exporting all the usage requirements to a target named proxywrapper-targets
install(TARGETS ${PROJECT_NAME} EXPORT proxywrapper-targets
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)

# Install the public header files
install(FILES include/ProxyWrapper.h DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/${PROJECT_NAME})

# Write the usage requirements exported above to a file. Allows other cmake-aware projects to consume this library easily.
install(EXPORT proxywrapper-targets
    FILE proxywrapper-targets.cmake
    NAMESPACE PROXYWRAPPER::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/${PROJECT_NAME}
)

# Install the config file.
# proxywrapper-config.cmake file enables automatic specification of our depedencies when other projects include the proxywrapper.
install(FILES "cmake/proxywrapper-config.cmake" "cmake/Findlibproxy.cmake"
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/${PROJECT_NAME}
)
