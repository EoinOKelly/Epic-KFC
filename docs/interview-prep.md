# Interview / viva prep (cryptography)

Short answers if the panel pushes hard.

## “Did you roll your own crypto?”

**Policy:** use standard libraries wherever they exist (`argon2`, Node `crypto`; production E2EE should be **libsignal**).

**Current state:** primitives use `argon2` and Node `crypto`. X3DH and the double ratchet come from `@privacyresearch/libsignal-protocol-typescript`. User plaintext is wrapped in **AES-256-GCM** before the ratchet (the port’s internal CBC+HMAC is not our AEAD boundary). Migration to `@signalapp/libsignal-client` is the hardening path for production and PQXDH.

## “Why not HPKE?”

The brief lists HPKE as an example. We use **X3DH** for async pre-key delivery, which is Signal’s standard for the same problem (shared secret + authenticated setup). HPKE Mode_Auth is a justified alternative; we’d map X25519 + Ed25519 keys into HPKE if we refactored.

## “Quantum secure?”

**AES-256-GCM**: good symmetric choice; Grover → ~128-bit effective strength. **X25519**: not post-quantum; recorded traffic could be decrypted later by a capable adversary. We don’t implement PQXDH.

## “Why AES-GCM instead of Signal’s cipher?”

CS4455 forbids encrypt-then-MAC and requires standard AEAD. GCM is listed in the brief. We keep Signal’s **ratchet keys**, change only the **payload** primitive.

## “What if the server is evil?”

Cannot decrypt ciphertext without keys. Can **drop** messages, serve **fake pre-keys** to new users (mitigated by **TOFU** if users verify fingerprints), and learn **metadata**. Cannot undetectably **alter** ciphertext without GCM failure.

## “Argon2 parameters?”

64 MiB memory, 3 iterations, 4 parallelism (OWASP strong interactive tier).

## “Nonce reuse?”

Fresh 12-byte IV per `encryptMessage`; ratchet rotates message keys. No IV reuse under the same key.

## “How does C++ use your code?”

Node package for backend; C++ should implement the same wire format and algorithms (OpenSSL/libsodium) or document a deliberate bridge. E2EE must run **on the client**, not only on server.

## “How does blockchain fit?”

Client hashes conversation canonical form with **keccak256**, anchors on Sepolia. Separate from E2EE: integrity audit, not confidentiality.

## Limitations to volunteer (shows understanding)

- No formal audit of ratchet code  
- No group E2EE  
- No PQXDH  
- TOFU requires UI; first contact is trust-on-first-use literally  
- Application-layer replay needs message IDs / dedup on server  
