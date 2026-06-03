# Threat model (summary)

Full narrative, primitive citations, and protocol diagrams are in [cryptography.md](./cryptography.md). This page is a quick reference for interviews.

## Attackers (CS4455 brief)

| Class | Capability |
|-------|------------|
| **A. Passive network** | Read client-server traffic |
| **B. Active network** | Modify, drop, replay, inject traffic |
| **C. Honest-but-curious server** | Follows protocol; logs ciphertext and metadata |
| **D. Compromised server** | Full DB; arbitrary API responses |

## Cryptographic defences

| Defence | A | B | C | D |
|---------|---|---|---|---|
| Past ciphertext confidential | Yes | Yes | Yes | Yes |
| Tampering detected (AEAD) | n/a | Yes | Yes | Yes |
| Sender bound to keys (signed pre-keys + TOFU) | n/a | Yes | Yes | Yes* |
| Forward secrecy after chain step | Yes | Yes | Yes | Yes |

\*TOFU: clients pin identity keys and block sends on `key_changed`.

## Documented limits (not cipher failures)

| Topic | Notes |
|-------|--------|
| Metadata privacy | Server sees who/when; standard for relay-based E2EE |
| Delivery guarantee | Out of scope for E2EE; server can drop rows |
| First-contact MITM | Mitigated when user runs `/trust` before sending |

## Passwords vs message keys

- **Argon2id** protects the login if the password table leaks.
- **X3DH / ratchet** supplies message keys; not derived from the password.
- Local private keys: `encryptPrivateKeyForStorage` under HKDF-derived keys (client duty).

## Blockchain

- Sepolia stores **keccak256** digests (Merkle roots), not plaintext.
- Public chain data proves integrity of what you anchored, not confidentiality.
