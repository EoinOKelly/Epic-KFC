cmake_minimum_required(VERSION 3.16)
project(client LANGUAGES CXX)

include(qt.cmake)

find_package(QT NAMES Qt6 Qt5 REQUIRED COMPONENTS Core Network)
find_package(Qt${QT_VERSION_MAJOR}
    COMPONENTS
        Core
        Network
)

option(CLIENT_REQUIRE_OPENSSL "Require OpenSSL-backed native crypto for real mode" ON)

set(CLIENT_OPENSSL_CACHE_VARIABLES
    OPENSSL_ROOT_DIR
    OPENSSL_INCLUDE_DIR
    OPENSSL_CRYPTO_LIBRARY
    OPENSSL_SSL_LIBRARY
    LIB_EAY_DEBUG
    LIB_EAY_RELEASE
    LIB_EAY_LIBRARY_DEBUG
    LIB_EAY_LIBRARY_RELEASE
    SSL_EAY_DEBUG
    SSL_EAY_RELEASE
    SSL_EAY_LIBRARY_DEBUG
    SSL_EAY_LIBRARY_RELEASE
)

set(CLIENT_OPENSSL_CACHE_USES_MINGW FALSE)
foreach(CLIENT_OPENSSL_CACHE_VARIABLE ${CLIENT_OPENSSL_CACHE_VARIABLES})
    if(DEFINED ${CLIENT_OPENSSL_CACHE_VARIABLE}
        AND "${${CLIENT_OPENSSL_CACHE_VARIABLE}}" MATCHES "[Mm][Ii][Nn][Gg][Ww]")
        set(CLIENT_OPENSSL_CACHE_USES_MINGW TRUE)
    endif()
endforeach()

if(MSVC AND CLIENT_OPENSSL_CACHE_USES_MINGW)
    foreach(CLIENT_OPENSSL_CACHE_VARIABLE ${CLIENT_OPENSSL_CACHE_VARIABLES})
        unset(${CLIENT_OPENSSL_CACHE_VARIABLE} CACHE)
    endforeach()
endif()

find_package(OpenSSL QUIET COMPONENTS Crypto)

if(NOT OpenSSL_FOUND AND MINGW AND EXISTS "C:/Qt/Tools/mingw1310_64/opt")
    set(OPENSSL_ROOT_DIR "C:/Qt/Tools/mingw1310_64/opt" CACHE PATH "OpenSSL root directory")
    find_package(OpenSSL QUIET COMPONENTS Crypto)
endif()

if(CLIENT_REQUIRE_OPENSSL AND NOT OpenSSL_FOUND)
    message(FATAL_ERROR
        "OpenSSL Crypto was not found. Real mode requires OpenSSL-backed native crypto. "
        "Install OpenSSL 3 development libraries built for the active compiler, then rerun CMake. "
        "For a mock-only build, configure with -DCLIENT_REQUIRE_OPENSSL=OFF."
    )
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
    src/crypto/MockCryptoProvider.cpp
    src/crypto/MockCryptoProvider.h
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
    src/support/EthereumHash.cpp
    src/support/EthereumHash.h
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
else()
    target_compile_definitions(client_core
        PUBLIC
            CLIENT_HAS_OPENSSL=0
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

set_target_properties(${PROJECT_NAME}
    PROPERTIES
        VS_DEBUGGER_COMMAND_ARGUMENTS "$<$<CONFIG:Debug>:--debug-errors>"
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

