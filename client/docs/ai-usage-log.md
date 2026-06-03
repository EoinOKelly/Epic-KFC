# AI Usage Log - C++ Client

Date: 2026-06-03

Component: Qt C++ console client

Purpose: This document records meaningful AI-assisted work on the C++ client for
the CS4455 Epic secure messaging project. It is written as a submission artefact,
not as a raw chat transcript. Prompt wording has been cleaned up, and passwords,
private messages, and sensitive local details have been removed.

## Scope

AI assistance in this log was focused on the `client/` C++ component. Other project
areas were only inspected when needed to understand API contracts, cryptography
compatibility, blockchain verification, or documentation expectations.

The client remained a Qt Console Application throughout. The final design uses Qt
for the event loop, console integration, signals/slots, TLS networking, and JSON
boundary work, while the core client logic uses modern C++ and STL containers
where suitable.

## Architecture And Planning

- Prompt summary: inspect the existing C++ client and design a high-mark,
  event-driven Qt console messaging client.
- Accepted output:
  - kept `QCoreApplication` as the runtime.
  - introduced an event-driven architecture with a console input worker, slash
    command parser, command router, controller, event bus, services, and presenter.
  - kept backend, crypto, trust, storage, and fidelity behind interfaces so mock
    and real implementations can be swapped cleanly.
  - retained a local mock mode for demonstration and tests.
- Corrections made after review:
  - all user actions were standardised as slash commands.
  - the client stayed console-based, matching the Qt Console Application brief.
  - backend, database, and blockchain implementation work stayed outside the C++
    client scope.

## Real Backend And Startup Behaviour

- Prompt summary: integrate the client with the production backend while keeping a
  debug/mock fallback.
- Accepted output:
  - real mode became the default launch mode.
  - default production API URL became `https://kfc.theburkenator.com/api/v1`.
  - `--debug` starts mock mode without backend dependencies.
  - `--api-url` can override the production URL in real mode.
  - plain HTTP URLs are rejected for real mode.
  - `--debug-errors` enables technical error detail for development.
- Corrections made after review:
  - conflicting startup flags are rejected with clear errors.
  - normal user-facing errors hide raw HTTP, Qt, and validation internals.
  - technical backend details are reserved for debug error output.

## Backend Endpoint Integration

- Prompt summary: use the deployed API routes rather than mocks for production
  testing.
- Accepted output:
  - real auth flow for registration, login, logout, and current-user lookup.
  - username lookup through the backend once the route became available.
  - key upload and pre-key bundle retrieval for trusted recipients.
  - message send, received list, sent list, forwarding, revocation, deletion, and
    anchor verification calls.
  - local conversation grouping where the backend does not expose a dedicated
    conversations endpoint.
- Corrections made after review:
  - first-use one-time-prekey conflicts are treated as recoverable, because the
    device can already have uploaded key material.
  - request timeout handling was added so backend outages do not appear as a
    silent hang.
  - HTTP/2 was disabled for the REST gateway after first-request stream issues
    caused intermittent closed-reply reads.

## Native Crypto Path

- Prompt summary: implement native C++ cryptography compatible with the project
  protocol rather than relying on placeholder crypto.
- Accepted output:
  - OpenSSL-backed native crypto adapter for key generation, signing, shared secret
    derivation, HKDF/HMAC, AES-GCM, and random bytes.
  - local device keys and ratchet/session material stored in encrypted local state.
  - TOFU trust pins for recipient identity keys.
  - local sender-copy ciphertext so sent messages can be read locally without
    storing plaintext.
- Corrections made after review:
  - the second-message risk was identified: later messages could omit the X3DH
    information that the decrypt path expected.
  - the client crypto/session path was adjusted so received messages can establish
    or reuse the needed state instead of only passing first-message tests.
  - old sent messages without a local sender copy still show a clear placeholder,
    because the sender cannot decrypt recipient-only ciphertext.

## C++ Style And Assessment Requirements

- Prompt summary: clean up C++ style and demonstrate modern C++ features required
  by the module.
- Accepted output:
  - C++20 target.
  - C#/Java-style brace placement.
  - cross-platform CMake project structure.
  - `std::vector`, `std::map`, `std::set`, `std::unordered_map`, `std::optional`,
    smart pointers, references, and RAII used where suitable.
  - Qt containers kept only where Qt API signatures require them.
  - core validation, local state, command models, message lists, and conversation
    data moved toward STL-friendly types.
- Corrections made after review:
  - unnecessary anonymous namespace usage in `main.cpp` was removed.
  - magic strings and numbers were reduced through named constants.
  - complex conditions were broken into named boolean variables where clarity
    improved.
  - line-ending consistency issues in the client were corrected.

## IRC-Like User Flow

- Prompt summary: make the console flow feel more like an IRC-style messaging
  client while staying within the brief.
- Accepted output:
  - `/msg <username>` enters a conversation.
  - `/read <username> [page]` opens a paginated conversation log.
  - `/back` returns to the main menu.
  - while inside a conversation, plain text sends a message to the active person.
  - `/send <username>` remains available for explicit one-off composition.
  - `/conversations` lists people with cached message history.
  - `/inbox` lists people with unread received messages.
- Corrections made after review:
  - operations such as sending, reading, revoking, deleting, exporting, and
    verifying now show progress text while work is running.
  - the prompt is suppressed while commands are in flight so users do not think an
    operation has finished early.
  - accidental prompt text is not captured as message content.

## Message Reading And Local Storage

- Prompt summary: make conversation history useful without weakening local
  security.
- Accepted output:
  - received messages are decrypted from their normal wire payload.
  - sent messages are displayed from local sender-copy ciphertext where available.
  - plaintext message bodies are not serialised into local state.
  - account-scoped state paths prevent one account from trying to decrypt another
    account's local state.
  - sessions, usernames, trust pins, device keys, prekeys, local tombstones, and
    cached messages persist across restarts after the local state password is
    supplied.
- Corrections made after review:
  - multi-device sent-message sync was documented as a limitation until the
    backend supports sender/device copies.
  - old messages from before the sender-copy change remain unrecoverable on the
    sender side unless another valid local copy exists.

## Verification And Blockchain Fidelity

- Prompt summary: ensure `/verify` works for message IDs and can be used by people
  who are not logged in.
- Accepted output:
  - `/verify <messageId>` is available without an authenticated session.
  - the client retrieves public message anchor metadata from the backend.
  - the client calls the public blockchain verification route with anchor data.
  - pending, confirmed, missing, and failed verification states are presented in
    user-friendly language.
- Corrections made after review:
  - an earlier logged-out verification path incorrectly depended on the protected
    message endpoint. This was removed.
  - digest reconstruction from local message content was avoided for public
    verification because it can drift from backend canonical anchoring.
  - malformed or incomplete transaction data is treated as pending or unavailable
    status rather than exposing raw schema errors in normal mode.

## Revocation, Deletion, And Cache Reconciliation

- Prompt summary: fix cases where revoked or deleted messages still appeared in
  conversation views.
- Accepted output:
  - local tombstones track deleted and revoked message IDs.
  - conversation views hide locally deleted or revoked messages.
  - message-list refresh reconciles local cache with server-visible messages so
    stale cached records are not shown as active.
- Corrections made after review:
  - backend behaviour was inspected to separate API behaviour from client cache
    behaviour.
  - C++ client changes were kept local to the client rather than modifying backend
    code.

## Download And Export Flow

- Prompt summary: simplify message export so users do not need to provide a path.
- Accepted output:
  - `/download <messageId>` exports the decrypted message to the directory where
    the program is running.
  - generated export names use the message ID so the output is predictable.
  - tokens, private keys, local state, and ratchet material are never exported.
- Corrections made after review:
  - directory arguments such as `C:\Users\...\Downloads` or `./` were removed from
    the command model because users expected the client to choose the file name.

## Release Build And Runtime Deployment

- Prompt summary: diagnose why Debug ran but Release failed at startup on Windows.
- Accepted output:
  - identified a Windows runtime DLL mismatch where Release loaded an unrelated
    Qt DLL from the system `PATH`.
  - copied the correct Qt and OpenSSL runtime DLLs next to the built executable.
  - updated CMake post-build deployment so Qt runtime libraries and platform/TLS
    plugins are copied for Windows builds.
- Corrections made after review:
  - Release smoke testing was performed with mock/debug mode and `/exit` after
    runtime deployment.
  - the log avoids claiming a fully packaged installer; it records the executable
    runtime deployment work that was actually done.

## Client Documentation

- Prompt summary: add and improve client documentation for building, running,
  testing, and explaining the C++ component.
- Accepted output:
  - client README with Windows, Linux, CMake, Qt, OpenSSL, and Visual Studio notes.
  - client documentation in `client/docs/client-docs.md`.
  - AI usage log in `client/docs/ai-usage-log.md`.
- Corrections made after review:
  - documentation was kept focused on what the client actually implements.
  - stale statements about the C++ crypto path being unfinished were removed from
    client-facing notes.
  - limitations are listed explicitly so the presentation does not overclaim.

## Validation Recorded

The following validation commands were used during the client work:

```powershell
$env:PATH='C:\Qt\Tools\mingw1310_64\bin;C:\Qt\6.9.1\mingw_64\bin;' + $env:PATH; cmake --build client\out\build\mingw-debug --target client_tests client --parallel 4
```

```powershell
$env:PATH='C:\Qt\Tools\mingw1310_64\bin;C:\Qt\6.9.1\mingw_64\bin;C:\Qt\Tools\mingw1310_64\opt\bin;' + $env:PATH; client\out\build\mingw-debug\client_tests.exe
```

```powershell
cmd.exe /c client\out\build-vs-client.bat
```

```powershell
$env:PATH='C:\Qt\6.9.1\msvc2022_64\bin;C:\Users\Cian\source\repos\Epic-KFC\client\out\vcpkg_installed\x64-windows\bin;' + $env:PATH; client\out\build\debug\client_tests.exe
```

```powershell
"/exit" | client\out\build\release\client.exe --debug
```

Known validation notes:

- One Visual Studio relink failed while the executable was still open, which is a
  Windows file-lock issue rather than a compile error.
- Some production behaviours depend on the deployed backend and blockchain worker
  being available.
- Manual real-mode testing was used throughout to confirm login, trust, send,
  read, conversation listing, deletion/revocation display, download, and
  verification behaviour against production routes.

## AI Output Corrected Or Rejected

- Early architecture advice assumed backend and crypto contracts were unknown.
  This was replaced once the actual API and crypto context were available.
- An initial verification approach required authentication because it used a
  protected message route. This was corrected so public fidelity verification can
  work for logged-out users.
- Some early UI flow behaved like isolated command execution. It was changed into
  conversation-oriented input with `/msg`, `/read`, and `/back`.
- Raw HTTP, schema, and Qt network errors initially leaked into the normal user
  interface. These are now hidden unless debug error output is enabled.
- Plaintext local sent-message caching was rejected in favour of local
  sender-copy ciphertext.
- Attempts to treat deleted or revoked message display as purely a backend issue
  were corrected by adding client cache reconciliation and tombstones.

## Remaining Limitations To Explain

- Sender-copy ciphertext is local to the current device. Reading sent messages on
  another device still needs backend support for sender/device message copies.
- The C++ client depends on production backend route availability for real-mode
  login, username lookup, key relay, message relay, revocation/deletion, and
  verification.
- Blockchain verification depends on the backend exposing public anchor metadata
  and the blockchain worker submitting confirmation data.
- Plaintext can exist briefly in process memory while the user composes, sends,
  decrypts, displays, or exports a message. It should not be written to local
  state or sent to the backend as plaintext.
- Mock mode remains important as a reliable demonstration fallback if production
  services are unavailable during marking.
