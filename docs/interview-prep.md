# Interview / viva prep (cryptography)

Short answers if the panel pushes hard.

## “Did you roll your own crypto?”

We use **argon2** and **Node crypto** for primitives. We implemented **Signal’s X3DH and Double Ratchet key schedule** ourselves; message bodies use **AES-256-GCM** per the brief, not Signal’s CBC+HMAC. That protocol wiring is the main custom surface — we cite the Signal specs and document that libsignal would be the production choice.

## “Why not HPKE?”

The brief lists HPKE as an example. We use **X3DH** for async pre-key delivery, which is Signal’s standard for the same problem (shared secret + authenticated setup). HPKE Mode_Auth is a justified alternative; we’d map X25519 + Ed25519 keys into HPKE if we refactored.

## “Quantum secure?”

**AES-256-GCM**: good symmetric choice; Grover → ~128-bit effective strength. **X25519**: not post-quantum; recorded traffic could be decrypted later by a capable adversary. We don’t implement PQXDH.

## “Why AES-GCM instead of Signal’s cipher?”

CS4455 forbids encrypt-then-MAC and requires standard AEAD. GCM is listed in the brief. We keep Signal’s **ratchet keys**, change only the **payload** primitive.

## “What if the server is evil?”

Cannot decrypt ciphertext without keys. Can **drop** messages, serve **fake pre-keys** to new users (mitigated by **TOFU** if users verify fingerprints), and learn **metadata**. Cannot undetectably **alter** ciphertext without GCM failure.

## “Argon2 parameters?”

64 MiB memory, 3 iterations, 4 parallelism — OWASP strong interactive tier; balances GPU resistance and login latency.

## “Nonce reuse?”

Fresh random 12-byte IV per `encryptMessage` call; ratchet gives a new message key per message. Reusing IV+key would break GCM — we avoid by construction.

## “How does C++ use your code?”

Node package for backend; C++ should implement the same wire format and algorithms (OpenSSL/libsodium) or document a deliberate bridge. E2EE must run **on the client**, not only on server.

## “How does blockchain fit?”

Client hashes conversation canonical form with **keccak256**, anchors on Sepolia. Separate from E2EE — integrity/public audit, not confidentiality.

## Limitations to volunteer (shows understanding)

- No formal audit of ratchet code  
- No group E2EE  
- No PQXDH  
- TOFU requires UI; first contact is trust-on-first-use literally  
- Application-layer replay needs message IDs / dedup on server  
