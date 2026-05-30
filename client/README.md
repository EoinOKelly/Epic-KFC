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

Mock and real integrations are selected at startup:

- `--mode mock`: local demo mode with mock gateways and mock crypto-shaped
  payloads.
- `--mode real --api-url https://host/api/v1`: FastAPI integration over TLS.

Real mode requires HTTPS and does not disable Qt certificate validation.

## Build

Required dependencies:

- CMake 3.16+
- A C++20 compiler
- Qt 6 or Qt 5 with Core and Network
- OpenSSL 3 development libraries for real native crypto

Windows with Qt MinGW example:

```powershell
$env:PATH='C:\Qt\Tools\mingw1310_64\bin;C:\Qt\6.9.1\mingw_64\bin;' + $env:PATH
cmake -S client -B client\out\build\mingw-debug -G "MinGW Makefiles" -DCMAKE_PREFIX_PATH=C:\Qt\6.9.1\mingw_64 -DCLIENT_BUILD_TESTS=ON
cmake --build client\out\build\mingw-debug --parallel 4
```

Linux example:

```bash
cmake -S client -B client/out/build/debug -DCLIENT_BUILD_TESTS=ON
cmake --build client/out/build/debug --parallel 4
```

## Run

Mock mode:

```bash
client --mode mock
```

Real mode:

```bash
client --mode real --api-url https://localhost:8000/api/v1 --device-id 1
```

Optional:

```bash
--state-path path/to/client-state.json
```

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
/read <messageId>
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

Mock mode resolves usernames locally. Real mode accepts UUIDs today and is wired for
`GET /api/v1/users/by-username/{username}` once the backend exposes username lookup
with active device metadata.

## Security Notes

- Real mode uses `HttpAuthGateway`, `HttpKeyGateway`, and `HttpMessageGateway`
  against `/auth/*`, `/keys/*`, and `/messages/*`.
- The HTTP client retries one protected request after a `401` by calling
  `/auth/refresh`, then persists rotated tokens through the encrypted local store.
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
