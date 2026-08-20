cmake_minimum_required(VERSION 3.14)
project(chatbot_sdk VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)

include_directories(include)

add_library(chatbot_sdk INTERFACE)
target_include_directories(chatbot_sdk INTERFACE include)
