# C++ Client Documentation

Date updated: 2026-06-03

## Purpose

The `client/` folder is the assessed C++ component for the CS4455 secure
messaging application. It is a Qt Console Application built with C++20, CMake,
Qt Core, Qt Network, and OpenSSL-backed native cryptography.

The client is not a throwaway launcher. It is a working secure-messaging client
that:

- registers and logs in users through the FastAPI backend
- uploads device public keys and public one-time prekeys
- resolves usernames through the backend user directory
- sends, receives, lists, reads, forwards, revokes, deletes, downloads, and
  verifies messages
- encrypts outgoing plaintext before it reaches the backend
- decrypts received ciphertext locally
- stores tokens, private keys, one-time prekeys, trust pins, and cached messages
  in a local JSON store with secret protection in real mode
- connects to the team backend over HTTPS and keeps Qt certificate validation
  enabled
- reports blockchain fidelity anchor status through backend verification routes

This document is written against the C++ rubric. It should be read with:

- `client/README.md` for build, run, command, and validation instructions
- `docs/security/crypto_cpp_threat_model.pdf` for client-side crypto and local
  storage threats
- `docs/backend_docs/security/backend_threat_model.pdf` for backend, database,
  and API security controls
- `docs/backend_docs/api/api_contract.pdf` for the API contract the C++ client
  calls

## Rubric Mapping

| C++ rubric criterion | Evidence in this client |
| --- | --- |
| C++ component and project integration | The Qt console client integrates with the secure messaging API, key relay, local E2EE, local state, and blockchain verification status. |
| Code structure and organisation | Code is split across `.h` and `.cpp` files by responsibility: app routing, console UI, services, gateways, crypto, storage, domain models, and support utilities. |
| Functions, classes, and OOP design | Classes model client concepts such as controller, command router, services, gateways, crypto providers, local store, messages, sessions, and trust pins. Interfaces separate real and mock implementations. |
| Modern C++, memory safety, documentation, and interview understanding | Uses C++20, STL containers, `std::optional`, `std::vector`, `std::set`, `std::unordered_map`, `std::function`, references, RAII-style Qt ownership, and `Result<T>` error returns. Build/run docs and AI usage notes are included. |

## High-Level Runtime Flow

```text
main.cpp
  -> StartupConfigParser
  -> real or mock dependency setup
  -> ConsoleInputWorker
  -> SlashCommandParser
  -> CommandRouter
  -> ClientController
  -> SessionService / KeyService / MessageService
  -> gateway, crypto, and JsonLocalStore interfaces
  -> EventBus
  -> ConsolePresenter
```

The user interacts with slash commands. The router validates command shape and
input mode, the controller delegates to services, services call gateways and
crypto/local-store providers, and all user-facing output is emitted through the
event bus to the presenter.

## Main Files And Responsibilities

| Path | Responsibility |
| --- | --- |
| `client/src/main.cpp` | Creates the Qt application, parses startup config, chooses real/mock dependencies, and wires services together. |
| `client/src/app/StartupConfig.*` | Parses command-line flags such as `--debug`, `--mode`, `--api-url`, `--device-id`, and `--debug-errors`; rejects insecure real-mode URLs. |
| `client/src/app/SlashCommandParser.*` | Turns user input into typed slash commands and arguments. |
| `client/src/app/CommandRouter.*` | Owns input modes such as command mode, password prompts, and multi-line message composition. |
| `client/src/app/ClientController.*` | Coordinates high-level user actions and delegates to services. |
| `client/src/app/EventBus.*` | Emits typed Qt signals for status, errors, messages, conversations, and prompts. |
| `client/src/console/ConsoleInputWorker.*` | Reads console input without blocking the main Qt event loop. |
| `client/src/console/ConsolePresenter.*` | Converts events into clear console output. |
| `client/src/domain/Models.*` | Holds enums and value types such as sessions, keys, messages, anchors, and conversations. |
| `client/src/services/Services.*` | Implements session, key, trust, message, forwarding, deletion, local read, download, and verification workflows. |
| `client/src/gateways/Gateways.*` | Defines interfaces and mock implementations for auth, key, user-directory, message, and crypto boundaries. |
| `client/src/gateways/HttpGateways.*` | Implements real Qt Network calls to the FastAPI backend and refresh-token retry behaviour. |
| `client/src/crypto/NativeSignalCryptoProvider.*` | Implements OpenSSL-backed key generation, signed prekey validation, X25519/HKDF, AES-256-GCM, and tamper rejection. |
| `client/src/crypto/MockCryptoProvider.*` | Provides mock-only demo payloads; this is intentionally not production security code. |
| `client/src/storage/JsonLocalStore.*` | Persists account state, device keys, prekeys, trust pins, known users, cached messages, local sender copies, and deletion/revocation tombstones. |
| `client/src/support/Result.h` | Provides explicit success/failure returns with typed `ClientError` values. |
| `client/src/support/ClientConstants.h` | Centralises user-facing text, API constants, crypto constants, and command names. |
| `client/src/support/EthereumHash.*` | Supports local Ethereum/Keccak-style hash handling used by fidelity verification support. |
| `client/tests/client_tests.cpp` | Focused regression tests for parser, startup validation, crypto, storage, and blockchain verification flow. |

## C++ Classes And Design Rationale

### Controller And Routing

`CommandRouter` keeps the console interaction state. It knows whether the user is
typing a command, a password, or a multi-line message. This keeps parsing and
input-flow concerns separate from networking and cryptography.

`ClientController` is the high-level coordinator. It receives typed commands and
calls `SessionService`, `KeyService`, or `MessageService`. It does not implement
HTTP, encryption, or storage directly.

### Services

`SessionService` owns the current authenticated session in memory and persists or
clears tokens through `JsonLocalStore`.

`KeyService` owns client key setup and trust decisions. It loads or creates local
device keys, uploads public key material, fetches recipient bundles, verifies
signed prekeys, and stores TOFU trust pins.

`MessageService` owns user-facing message workflows. It encrypts before sending,
decrypts for reading/download, forwards by re-encrypting, handles deletion and
revocation cache updates, and checks blockchain anchor status.

These services are separate because authentication, key management, and message
handling are different responsibilities. This makes the code easier to explain
and test.

### Gateways And Polymorphism

Gateway interfaces are used where polymorphism improves the design:

- `IAuthGateway`
- `IKeyGateway`
- `IUserDirectoryGateway`
- `IMessageGateway`
- `ICryptoProvider`

Real mode uses HTTP gateways and `NativeSignalCryptoProvider`. Mock mode uses
mock gateways and `MockCryptoProvider`. This split allows local demonstration and
tests without pretending that mock crypto is secure.

### Domain Models

The client uses value types for project concepts:

- `AuthSession`
- `DeviceKeyMaterial`
- `OneTimePreKey`
- `PreKeyBundle`
- `TrustPin`
- `LocalMessage`
- `BlockchainAnchor`
- `ConversationSummary`

These are plain structs because they mainly carry data between services, storage,
gateways, and UI events.

## Memory Management And Ownership

The client avoids owning raw pointers and manual `new`/`delete`.

- Long-lived dependencies are created in `main.cpp` and passed by reference into
  controllers and services.
- Qt `QObject` inheritance is used for event-driven classes and signal/slot
  behaviour.
- Service classes store non-owning references such as `EventBus&`,
  `IAuthGateway&`, `JsonLocalStore&`, and `SessionService&`. This is deliberate:
  `main.cpp` owns the objects for the lifetime of the application.
- Data such as sessions, messages, keys, and conversations is stored as normal
  values in STL containers or Qt value types.
- `std::optional` is used for values that may or may not exist, such as an
  authenticated session, a trust pin, a known user, a one-time prekey, or a
  cached message lookup.
- `std::function<void(Result<T>)>` is used for gateway callbacks so asynchronous
  operations can return either success or a typed client error.

This design is explainable in the interview: `main.cpp` owns the components,
services borrow them by reference, and sensitive data is copied only as value
types needed for the workflow.

## STL And Modern C++ Use

The client uses modern C++ where it makes the code clearer:

- `std::vector` for command arguments, message lists, prekey batches, and
  conversation logs.
- `std::set` for visible message IDs during cache reconciliation.
- `std::unordered_map` for mock gateway state and crypto send counters.
- `std::optional` for nullable values without raw pointers or sentinel strings.
- `std::function` for typed asynchronous gateway callbacks.
- `enum class` for command type, client mode, error codes, and message direction.
- references for dependency injection instead of global state.
- `const` parameters and helper functions where mutation is not needed.

Qt types such as `QString`, `QDateTime`, `QObject`, `QNetworkAccessManager`,
`QJsonObject`, and signals/slots are used where they fit Qt networking and event
handling.

## Secure Messaging Integration

### Backend Connectivity

Real mode talks to `https://kfc.theburkenator.com/api/v1` by default. The startup
parser rejects plain HTTP in real mode. Qt Network handles TLS and certificate
validation through the platform trust store; the client does not disable
certificate checks for the demo.

The HTTP gateways call backend endpoints for:

- registration and login
- access-token refresh and logout
- current-user lookup
- username resolution
- device key upload
- one-time prekey upload
- recipient prekey bundle fetch
- sent and received message listing
- message send, forward, revoke, delete, and fetch
- blockchain anchor fetch and verification

### Cryptography

Real mode requires OpenSSL-backed native crypto. The native provider uses:

- X25519 for key agreement material
- Ed25519 for signed prekey validation
- HKDF-SHA256 for deriving keys from shared secret material
- HMAC-SHA256 where needed for ratchet-style derivation
- AES-256-GCM for message encryption and tamper detection
- OpenSSL CSPRNG output for keys and IVs

The client encrypts plaintext locally before sending `wire_payload_json` to the
backend. If ciphertext, IV, AAD, or authentication tag is modified, AES-GCM
decryption fails and the message is not displayed as trusted plaintext.

### Local State

Real-mode local state protects sensitive fields before writing JSON. Protected
fields include:

- access tokens
- refresh tokens
- identity private keys
- signing private keys
- signed prekey private keys
- one-time prekey private keys
- trust pins
- local sender-copy ciphertext

The local store also scopes default state by authenticated account so switching
accounts on the same machine does not accidentally try to decrypt another
account's device keys.

### Blockchain Verification

The C++ client does not mine blocks or hold a wallet key. It asks the backend for
anchor metadata and reports whether the anchor is missing, pending, failed,
confirmed, or mismatched. The standalone fidelity UI remains the independent
place to recompute digest evidence from pasted content.

## User Commands

The client supports the following slash commands:

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
/msg <username> [message]
/send [message]
/read <username> [page]
/forward <messageId> <username>
/revoke <messageId>
/delete <messageId>
/download <messageId>
/trust <username>
/verify <messageId>
/sync
/cancel
/back
/exit
```

This command set directly supports the brief's expected operations: sign-up,
login, sent/received listing, message creation and sending, forwarding,
revocation, download, deletion, and integrity verification.

## Validation Evidence

The focused test command is:

```powershell
$env:PATH='C:\Qt\Tools\mingw1310_64\bin;C:\Qt\6.9.1\mingw_64\bin;C:\Qt\Tools\mingw1310_64\opt\bin;' + $env:PATH
client\out\build\mingw-debug\client_tests.exe
```

The tests cover:

- slash command parsing
- startup mode validation
- rejection of HTTP real-mode API URLs
- native device key generation
- signed prekey validation
- first-message encryption and decryption
- AES-GCM tamper rejection
- mock crypto isolation
- encrypted local-state save and reload
- account-scoped local state
- blockchain verification status handling for pending, confirmed, mismatch, and
  missing anchors

The broader build instructions are in `client/README.md` for MSVC, Qt MinGW,
Linux, and macOS.

## Known Limitations

- Persisted Double Ratchet session state is not complete in the C++ native crypto
  path. The current native tests cover first-message X3DH/AES-GCM behaviour and
  tamper rejection.
- Mock mode is for offline demonstration and tests only. It must not be described
  as secure cryptography.
- Local sender-copy ciphertext is currently local to the device that sent the
  message. Reading sent messages on another device needs future backend support
  for per-device sender copies.
- Local plaintext necessarily exists briefly in memory while the user composes,
  encrypts, decrypts, or displays a message. It should not be written to local
  state.
- Verification depends on backend anchor metadata and the blockchain worker
  confirming pending anchors.

## Interview Defence Points

- The C++ component is meaningful because it is a working client, not a wrapper
  around another program.
- The code is organised into focused files with `.h`/`.cpp` pairs and a CMake
  build.
- Classes model real project concepts: controller, router, services, gateways,
  crypto provider, local store, session, message, prekey bundle, trust pin, and
  blockchain anchor.
- Polymorphism is used only at integration boundaries where real and mock
  implementations differ.
- Memory ownership is simple: `main.cpp` owns long-lived objects; services borrow
  them by reference; data is stored in value types and STL containers.
- Real mode requires HTTPS and native OpenSSL crypto; mock mode is explicit.
- The client and backend threat models split responsibilities clearly: the
  backend authenticates and authorises, while the client protects plaintext and
  private key material.
- Limitations are documented honestly and should be explained before the examiner
  has to discover them.

