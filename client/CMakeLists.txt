cmake_minimum_required(VERSION 3.16)
project(client LANGUAGES CXX)

include(qt.cmake)

find_package(QT NAMES Qt6 Qt5 REQUIRED COMPONENTS Core Network)
find_package(Qt${QT_VERSION_MAJOR}
    COMPONENTS
        Core
        Network
)
find_package(OpenSSL QUIET)

if(NOT OpenSSL_FOUND AND WIN32 AND EXISTS "C:/Qt/Tools/mingw1310_64/opt")
    set(OPENSSL_ROOT_DIR "C:/Qt/Tools/mingw1310_64/opt" CACHE PATH "OpenSSL root directory")
    find_package(OpenSSL QUIET)
endif()
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)

set(CLIENT_CORE_SOURCES
    src/app/ClientController.cpp
    src/app/ClientController.h
    src/app/CommandRouter.cpp
    src/app/CommandRouter.h
    src/app/EventBus.cpp
    src/app/EventBus.h
    src/app/SlashCommandParser.cpp
    src/app/SlashCommandParser.h
    src/app/StartupConfig.cpp
    src/app/StartupConfig.h
    src/console/ConsoleInputWorker.cpp
    src/console/ConsoleInputWorker.h
    src/console/ConsolePresenter.cpp
    src/console/ConsolePresenter.h
    src/crypto/NativeSignalCryptoProvider.cpp
    src/crypto/NativeSignalCryptoProvider.h
    src/domain/Models.cpp
    src/domain/Models.h
    src/gateways/Gateways.cpp
    src/gateways/Gateways.h
    src/gateways/HttpGateways.cpp
    src/gateways/HttpGateways.h
    src/services/Services.cpp
    src/services/Services.h
    src/storage/JsonLocalStore.cpp
    src/storage/JsonLocalStore.h
    src/support/ClientConstants.h
    src/support/Result.h
)

add_library(client_core STATIC ${CLIENT_CORE_SOURCES})
target_compile_options(client_core
    PUBLIC
        $<$<CXX_COMPILER_ID:MSVC>:/std:c++20>
        $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-std=c++20>
)
target_include_directories(client_core
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/src
)
target_link_libraries(client_core
    PUBLIC
        Qt::Core
        Qt::Network
)

if(OpenSSL_FOUND)
    target_link_libraries(client_core
        PUBLIC
            OpenSSL::Crypto
    )
    target_compile_definitions(client_core
        PUBLIC
            CLIENT_HAS_OPENSSL=1
    )
endif()

add_executable(${PROJECT_NAME}
    src/main.cpp
)

target_link_libraries(${PROJECT_NAME}
    PRIVATE
        client_core
        Qt::Core
        Qt::Network
)

option(CLIENT_BUILD_TESTS "Build the Qt console client tests" ON)

if(CLIENT_BUILD_TESTS)
    enable_testing()

    add_executable(client_tests
        tests/client_tests.cpp
    )
    target_link_libraries(client_tests
        PRIVATE
            client_core
            Qt::Core
            Qt::Network
    )
    add_test(NAME client_tests COMMAND client_tests)
endif()

