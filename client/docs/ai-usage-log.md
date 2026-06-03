# AI Usage Log - C++ Client

Date: 2026-06-03

This log summarises meaningful AI-assisted work on the Qt C++ console client during
this chat. It is intended as submission evidence for the AI artefact requirement
and as a short record of what was accepted, corrected, and validated.

## Scope

The AI assistance was limited to the `client/` C++ component unless explicitly
noted for read-only inspection of project context. The client is a Qt Console
Application for the secure messaging project.

## Prompts And Outcomes

### Initial Client Architecture

- Prompt summary: review the existing `client/` directory and propose an
  event-driven Qt console messaging client architecture.
- Accepted output:
  - Qt `QCoreApplication` runtime.
  - console input worker to avoid blocking the Qt event loop.
  - slash-command parser and router.
  - event bus and presenter for user output.
  - service abstractions for auth, messages, keys, crypto, trust, local state, and
    fidelity.
- Corrections made after review:
  - all user commands were changed to slash commands.
  - the client was kept console-based rather than GUI-based.
  - backend, database, and crypto details were isolated behind interfaces until
    real contracts were available.

### Real Backend And Native Crypto Integration

- Prompt summary: extend the client design so it can run against either local mock
  services or the real production backend endpoints.
- Accepted output:
  - startup configuration with real mode and debug/mock mode.
  - production default API URL: `https://kfc.theburkenator.com/api/v1`.
  - HTTPS-only validation for real mode.
  - HTTP gateway classes for auth, user lookup, keys, messages, and verification.
  - native OpenSSL-backed crypto adapter.
  - mock mode retained for offline demonstration and tests.
- Corrections made after review:
  - real mode became the default startup path.
  - `--debug` became the user-facing mock/demo flag.
  - raw technical errors were hidden unless debug error output is enabled.
  - endpoint assumptions were revisited when backend routes changed.

### C++ Style And Assessment Requirements

- Prompt summary: improve the C++ code style and ensure the client demonstrates
  modern, assessable C++ practice.
- Accepted output:
  - C++20 target.
  - C#/Java-style braces.
  - reduced magic strings and numbers through constants.
  - improved variable names and simplified boolean logic.
  - line-ending consistency checks.
  - STL containers used in core logic where suitable.
  - Qt types retained where required by Qt APIs, signals, slots, and networking.
- Corrections made after review:
  - removed an unnecessary small anonymous namespace in `main.cpp`.
  - replaced avoidable Qt containers with STL equivalents in core code.
  - explained why Qt callback signatures still require types such as `QList`.

### IRC-Like Console Flow

- Prompt summary: refine the console interaction model so message flow feels more
  like an IRC-style conversation client.
- Accepted output:
  - `/msg <username>` and `/read <username> [page]` conversation flow.
  - prompt changes while inside a conversation.
  - plain text inside a conversation sends a message without requiring `/send`.
  - `/back` returns to the main menu.
  - `/conversations` lists people with cached conversation history.
  - `/inbox` lists people with unread received messages.
- Corrections made after review:
  - prompts were adjusted so users do not think background operations are finished
    while still running.
  - accidental prompt text was prevented from being captured as message content.
  - user-facing errors were made clearer and less technical.

### Message Reading, Local Storage, And Sender Copies

- Prompt summary: make sent messages readable in local conversation history without
  storing plaintext message bodies on disk.
- Accepted output:
  - removed local plaintext message caching.
  - stored local sender-copy ciphertext for messages sent from the current device.
  - `/read <username>` decrypts local sender-copy ciphertext for sent messages.
  - old sent messages without sender-copy ciphertext show a clear placeholder.
- Corrections made after review:
  - explained that multi-device sent-message sync still requires backend support
    for sender/device copies.
  - kept private keys and sensitive local fields encrypted at rest.

### Persistence Fixes

- Prompt summary: resolve persistence issues for restored sessions, trusted
  identities, known usernames, and local device state.
- Accepted output:
  - local state restore flow using a local state password.
  - persisted session, known usernames, trust pins, device keys, one-time prekeys,
    and cached message state.
- Corrections made after review:
  - account-scoped default state paths were introduced to avoid one account trying
    to decrypt another account's local state.
  - one-time prekey upload conflicts were treated as recoverable production
    behaviour rather than fatal startup failures.

### Network Reliability And Verification

- Prompt summary: improve network reliability, timeout handling, first-request
  stability, and blockchain verification behaviour.
- Accepted output:
  - request timeout handling.
  - clearer user-facing network errors.
  - suppressed noisy Qt network warnings from normal UI.
  - disabled HTTP/2 for authenticated REST after first-request stream issues.
  - avoided reading closed `QNetworkReply` devices.
  - verification no longer requires a logged-in session from the client side.
  - verification routes are called without auth headers now that the backend
    exposes them publicly.
- Corrections made after review:
  - removed stale logged-out verification text.
  - treated malformed or pending blockchain transaction data as pending fidelity
    status instead of exposing raw validation errors in normal mode.

### Revocation And Deletion Behaviour

- Prompt summary: correct conversation cache behaviour so revoked or deleted
  messages no longer appear after refresh.
- Accepted output:
  - local tombstones for deleted and revoked messages.
  - hidden locally deleted and revoked messages from conversation views.
  - reconciliation against full server-visible message lists so stale cached
    messages disappear after refresh.
- Corrections made after review:
  - backend behaviour was inspected read-only to determine whether filtering was
    expected from the API or client cache.
  - the C++ client was changed to reconcile cache state without modifying backend
    code.

### Event Loop And Input Responsiveness

- Prompt summary: investigate delayed command output where actions such as `/read`
  sometimes appeared to require an extra Enter key press.
- Accepted output:
  - console input worker signal delivery to the router was made an explicit
    `Qt::QueuedConnection`.
- Rationale:
  - console input is read from a worker thread, while command handling and network
    callbacks belong on the Qt event loop.
  - explicit queued delivery avoids relying on implicit cross-thread behaviour.

## Validation Recorded During The Chat

The following validation commands were run after relevant client changes:

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

Known validation note: one Visual Studio `client.exe` relink failed with a Windows
file-lock error while the executable was open. The MSVC test executable still ran
successfully in that validation pass.

## AI Output That Was Corrected Or Rejected

- Early plans assumed backend and crypto contracts were unknown. This was revised
  once real endpoints and native crypto requirements were supplied.
- A previous verification fallback said logged-out users had to log in because
  the backend protected anchor lookup. This became stale after verification was
  made public and was removed.
- Some early UI flow still behaved like isolated commands. It was revised into a
  conversation-oriented IRC-like flow.
- Some errors initially exposed low-level HTTP or Qt details. Normal mode was
  changed to show safer user-facing messages, with technical detail reserved for
  debug error output.

## Remaining Limitations To Explain

- Sender-copy ciphertext is local to the current device. Reading sent messages on
  a different device still requires future backend support for sender/device copy
  sync.
- Verification depends on the production backend and blockchain worker exposing
  public anchor and verification data.
- Local plaintext can exist briefly in memory while composing, encrypting, and
  displaying messages, but it should not be serialised to disk.
- The backend and blockchain components are owned outside this C++ client scope;
  the C++ client integrates with their exposed contracts.
