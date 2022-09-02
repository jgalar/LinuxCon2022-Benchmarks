cmake_minimum_required(VERSION 3.6.0)
project(workload)

find_package(LTTngUST)

set(CMAKE_CXX_FLAGS "-Wall -Wextra -pthread")
set(CMAKE_CXX_FLAGS_DEBUG "-g3 -O0")
set(CMAKE_CXX_FLAGS_RELEASE "-O3")

set (CMAKE_CXX_EXTENSIONS OFF)
set (CMAKE_CXX_STANDARD 20)
set (CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(src)
set(WORKLOAD_SOURCES src/workload.cpp src/tp.cpp)

add_executable(workload ${WORKLOAD_SOURCES})
target_link_libraries(workload LTTng::UST)