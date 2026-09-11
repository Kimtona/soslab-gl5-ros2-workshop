cmake_minimum_required(VERSION 3.10)
project(soslab_ethinfo CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Populated by `make` at the SDK root via a POST_BUILD step, not `make install`.
set(SOSLAB_ARCHIVE "" CACHE PATH "path to the SDK's _archive_ directory")
if(NOT SOSLAB_ARCHIVE)
    set(SOSLAB_ARCHIVE "${CMAKE_CURRENT_SOURCE_DIR}/../_archive_")
endif()

# The suffix is _x64 on every 64-bit target, arm64 included, because the SDK
# picks it from CMAKE_SIZEOF_VOID_P rather than the actual architecture.
find_library(SOSLAB_LIDAR_LIB
    NAMES Lidar_x64_release Lidar_x64_debug
    PATHS "${SOSLAB_ARCHIVE}/lib"
    NO_DEFAULT_PATH REQUIRED)

add_executable(soslab_ethinfo main.cpp)
target_include_directories(soslab_ethinfo PRIVATE
    "${SOSLAB_ARCHIVE}/include"
    "${SOSLAB_ARCHIVE}/include/nlohmann_json")
target_link_libraries(soslab_ethinfo PRIVATE "${SOSLAB_LIDAR_LIB}")
set_target_properties(soslab_ethinfo PROPERTIES
    BUILD_RPATH "${SOSLAB_ARCHIVE}/lib"
    INSTALL_RPATH "${SOSLAB_ARCHIVE}/lib")
