cmake_minimum_required (VERSION 3.8)

# cmake find module for the libproxy library and headers

include(FindPackageHandleStandardArgs)

find_path(
    PROXY_INCLUDE_DIR
    NAMES proxy.h
    PATH_SUFFIXES include
)

find_library(PROXY_LIBRARY proxy)

find_package_handle_standard_args(
    PROXY
    DEFAULT_MSG
    PROXY_INCLUDE_DIR
    PROXY_LIBRARY
)

if(PROXY_FOUND)
    set(PROXY_INCLUDE_DIRS ${PROXY_INCLUDE_DIR})
    set(PROXY_LIBRARIES ${PROXY_LIBRARY})

    if(NOT TARGET PROXY::proxy)
        add_library (PROXY::proxy INTERFACE IMPORTED)
        set_target_properties(
            PROXY::proxy
            PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "${PROXY_INCLUDE_DIRS}"
                       INTERFACE_LINK_LIBRARIES "${PROXY_LIBRARIES}"
        )
    endif()
endif()
