# Epic KFC Qt Console Client

This is the C++ client component for the secure messaging project. It is a Qt
Console Application using C++20, Qt Core, Qt Network, and OpenSSL-backed native
crypto for real mode.

## Architecture

Runtime flow:

```text
ConsoleInputWorker
  -> SlashCommandParser
  -> CommandRouter
  -> ClientController
  -> SessionService / KeyService / MessageService
  -> gateway, crypto, and JSON local-store interfaces
  -> EventBus
  -> ConsolePresenter
```

The client starts in real mode by default against the team HTTPS endpoint:

- `client`: FastAPI integration over TLS using
  `https://kfc.theburkenator.com/api/v1`.
- `client --debug`: local demo mode with mock gateways and mock crypto-shaped
  payloads. This also enables raw diagnostic errors.
- `client --debug-errors`: real mode with technical HTTP/Qt/backend details shown
  in error output for troubleshooting.
- `client --api-url https://host/api/v1`: real mode with an overridden backend
  URL.

Real mode requires HTTPS and does not disable Qt certificate validation.

## Build

The client is a CMake project. Build commands below are run from the repository
root unless stated otherwise.

Required dependencies on every OS:

- CMake 3.16+
- A C++20 compiler
- Qt 6 or Qt 5 with Core and Network
- OpenSSL 3 development libraries for real native crypto

Production builds require OpenSSL by default. A mock-only build can be configured
with `-DCLIENT_REQUIRE_OPENSSL=OFF`, but real mode will refuse to start without
native crypto.

### Windows: Visual Studio / MSVC

Use this path when building from Visual Studio or with the MSVC compiler.

MSVC real mode needs an MSVC-compatible OpenSSL install. The OpenSSL binaries
bundled under `C:\Qt\Tools\mingw*_64\opt` are MinGW libraries and cannot be
linked into the Visual Studio build.

Example using Qt for MSVC and vcpkg OpenSSL:

```powershell
vcpkg install openssl:x64-windows
cmake -S client -B client\out\build\debug -G Ninja -DCMAKE_PREFIX_PATH=C:\Qt\6.9.1\msvc2022_64 -DCMAKE_TOOLCHAIN_FILE=C:\path\to\vcpkg\scripts\buildsystems\vcpkg.cmake -DCLIENT_BUILD_TESTS=ON
cmake --build client\out\build\debug --parallel 4
```

Run the tests:

```powershell
$env:PATH='C:\Qt\6.9.1\msvc2022_64\bin;C:\Users\Cian\source\repos\Epic-KFC\client\out\vcpkg_installed\x64-windows\bin;' + $env:PATH
client\out\build\debug\client_tests.exe
```

This repository also includes the local helper used during development:

```powershell
cmd.exe /c client\out\build-vs-client.bat
```

### Windows: Qt MinGW

Use this path when using the MinGW compiler bundled with Qt.

```powershell
$env:PATH='C:\Qt\Tools\mingw1310_64\bin;C:\Qt\6.9.1\mingw_64\bin;' + $env:PATH
cmake -S client -B client\out\build\mingw-debug -G "MinGW Makefiles" -DCMAKE_PREFIX_PATH=C:\Qt\6.9.1\mingw_64 -DCLIENT_BUILD_TESTS=ON
cmake --build client\out\build\mingw-debug --parallel 4
```

Run the tests:

```powershell
$env:PATH='C:\Qt\Tools\mingw1310_64\bin;C:\Qt\6.9.1\mingw_64\bin;C:\Qt\Tools\mingw1310_64\opt\bin;' + $env:PATH
client\out\build\mingw-debug\client_tests.exe
```

### Linux

Install a C++ compiler, CMake, Qt Core/Network development packages, and OpenSSL
development headers. Package names vary by distribution.

Ubuntu/Debian example:

```bash
sudo apt update
sudo apt install build-essential cmake ninja-build qt6-base-dev libssl-dev
```

Fedora example:

```bash
sudo dnf install gcc-c++ cmake ninja-build qt6-qtbase-devel openssl-devel
```

Configure and build:

```bash
cmake -S client -B client/out/build/linux-debug -G Ninja -DCLIENT_BUILD_TESTS=ON
cmake --build client/out/build/linux-debug --parallel 4
```

Run the tests:

```bash
client/out/build/linux-debug/client_tests
```

### macOS

Install Xcode command-line tools, CMake, Qt, and OpenSSL. Homebrew is the simplest
setup path:

```bash
xcode-select --install
brew install cmake ninja qt openssl@3
```

Configure and build. `CMAKE_PREFIX_PATH` points CMake at Homebrew Qt, while
`OPENSSL_ROOT_DIR` points it at Homebrew OpenSSL:

```bash
cmake -S client -B client/out/build/macos-debug -G Ninja -DCMAKE_PREFIX_PATH="$(brew --prefix qt)" -DOPENSSL_ROOT_DIR="$(brew --prefix openssl@3)" -DCLIENT_BUILD_TESTS=ON
cmake --build client/out/build/macos-debug --parallel 4
```

Run the tests:

```bash
client/out/build/macos-debug/client_tests
```

## Run

Real mode using the default team backend:

```bash
client
```

Debug/mock mode:

```bash
client --debug
```

Real mode with an overridden backend:

```bash
client --api-url https://kfc.theburkenator.com/api/v1 --device-id 1
```

Optional:

```bash
--state-path path/to/client-state.json
--mode mock|real
--debug-errors
```

In real mode, the default local state is split by authenticated user so switching
accounts on the same machine does not try to decrypt another account's device
keys. Supplying `--state-path` opts into one explicit state file, which should be
unique per account unless the same local password is reused intentionally.

## Slash Commands

All actions start with `/`.

```text
/help
/register <username> <email>
/login <usernameOrEmail>
/logout
/whoami
/status
/conversations
/inbox
/sent
/msg <username>
/send <username>
/read <username> [page]
/forward <messageId> <username>
/revoke <messageId>
/delete <messageId>
/download <messageId> <path>
/trust <username>
/verify <messageId>
/sync
/cancel
/exit
```

`/register`, `/login`, `/msg`, and `/send` enter prompt modes. Message composition
accepts slash-prefixed body text until `/send` submits or `/cancel` aborts.

Mock mode resolves usernames locally. Real mode resolves usernames through the
production `GET /api/v1/users/by-username/{username}` endpoint and then uses the
returned user/device metadata for trust and message commands.

`/verify <messageId>` checks the backend blockchain anchor metadata for that
message. If the anchor is pending or failed, the client reports that plainly. If
the anchor is confirmed, the client calls `POST /api/v1/blockchain/verify` with
the stored digest metadata and reports whether the backend verification passed.
The standalone blockchain fidelity UI remains the place to recompute a digest
from pasted plaintext/conversation content.

## Security Notes

- Real mode uses `HttpAuthGateway`, `HttpKeyGateway`, and `HttpMessageGateway`
  against `/auth/*`, `/keys/*`, and `/messages/*`.
- The HTTP client retries one protected request after a `401` by calling
  `/auth/refresh`, then persists rotated tokens through the encrypted local store.
- Normal mode hides raw HTTP, Qt, and backend validation details behind safe
  user-facing error messages. Use `--debug-errors` only when collecting technical
  diagnostics.
- Native crypto uses OpenSSL for X25519, Ed25519, HKDF-SHA256, HMAC-SHA256,
  AES-256-GCM, and CSPRNG output.
- Mock mode uses `MockCryptoProvider`; it is intentionally not security code.
- Real-mode local state encrypts access tokens, refresh tokens, private device
  keys, one-time pre-key private keys, and trust pins before writing JSON.
- Local state currently derives its encryption key with OpenSSL
  PBKDF2-HMAC-SHA256 and AES-256-GCM because libsodium is not available in the
  client toolchain yet. Argon2id remains the preferred upgrade when libsodium is
  added.
- The native Signal adapter handles key generation, signed pre-key validation,
  first-message X3DH encryption/decryption, and AES-GCM tamper rejection. Persisted
  Double Ratchet session state and TypeScript golden-vector tests are still the
  next crypto integration step.

## Validation

Current focused test command:

```bash
client/out/build/mingw-debug/client_tests.exe
```

The tests cover parser basics, startup mode validation, HTTPS enforcement, native
first-message crypto round trip, AES-GCM tamper rejection, mock crypto payloads,
and encrypted local-state save/reload behaviour.
