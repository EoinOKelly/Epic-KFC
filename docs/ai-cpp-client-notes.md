# AI-Assisted C++ Client Notes

## Request

Implement the revised Qt Console C++ client plan with mock mode, real API mode,
native crypto, slash commands, and cross-platform C++ design.

## Accepted Design Decisions

- Kept the client as a `QCoreApplication` console app.
- Used a slash-command pipeline: parser, router, controller, services, gateways,
  event bus, and presenter.
- Split mock and real integrations behind gateway and crypto interfaces.
- Added real HTTP gateways for the current FastAPI `/api/v1` auth, key, and
  message endpoints.
- Required HTTPS in real mode and kept Qt certificate validation enabled.
- Used OpenSSL-backed native crypto for real mode instead of custom primitives.
- Added mock crypto only for local marking/demo mode.
- Added encrypted real-mode local JSON state for tokens, private key material,
  one-time pre-key private keys, and trust pins.

## Corrections Made During Implementation

- Replaced earlier mock/fallback crypto behaviour with a separate
  `MockCryptoProvider` so real mode cannot silently use non-vetted crypto.
- Added command argument validation after review found known commands could be
  silently ignored.
- Tightened real startup validation so localhost HTTP is rejected in real mode.
- Added tests after encrypted local-state work exposed a sandbox write-path issue;
  the test now writes inside the repository workspace and closes the file before
  cleanup on Windows.

## Known Limitations

- Local state uses OpenSSL PBKDF2-HMAC-SHA256 plus AES-256-GCM. Argon2id via
  libsodium is still preferred when that dependency is added.
- Native crypto currently covers first-message X3DH/ratchet encryption and
  decryption. Persisted Double Ratchet session state and TypeScript golden vectors
  remain to be implemented.
- Backend integration has request construction and token refresh support, but it
  still needs mocked-network unit tests and an end-to-end run against a live
  deployed API.

## Validation Performed

- Configured and built the Qt client tests with CMake and MinGW Qt.
- Ran `client_tests.exe`; tests passed for parser, startup validation, HTTPS
  enforcement, native crypto round trip, tamper rejection, mock crypto, and
  encrypted local-state reload.
