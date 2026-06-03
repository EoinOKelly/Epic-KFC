# Threat model (summary)

Full narrative, primitive citations, and protocol diagrams are in [cryptography.md](./cryptography.md). This page is a quick reference for interviews.

## Attackers (CS4455 brief)

| Class | Capability |
|-------|------------|
| **A. Passive network** | Read client-server traffic |
| **B. Active network** | Modify, drop, replay, inject traffic |
| **C. Honest-but-curious server** | Follows protocol; logs ciphertext and metadata |
| **D. Compromised server** | Full DB; arbitrary API responses |

## Guarantees (E2EE layer)

| Property | A | B | C | D |
|----------|---|---|---|---|
| Message confidentiality (old ciphertext) | Yes | Yes | Yes | Yes* |
| Ciphertext integrity | n/a | Yes | Yes | Yes |
| Sender authenticity | n/a | Partial** | Partial** | Partial** |
| Metadata privacy | No | No | No | No |
| Forward secrecy (after ratchet) | Yes | Yes | Yes | Yes† |
| Prevent server dropping mail | No | No | No | No |
| Prevent first-contact MITM without TOFU | No | No | No | No |

\*Server never held private keys.  
\**Signed pre-keys + TOFU; not PKI.  
†Depends on ratchet state not being stolen.

## Passwords vs message keys

- **Argon2id** protects the login if the password table leaks.
- **X3DH / ratchet** supplies message keys; not derived from the password.
- Local private keys: `encryptPrivateKeyForStorage` under HKDF-derived keys (client duty).

## Blockchain

- Sepolia stores **keccak256** digests (Merkle roots), not plaintext.
- Public chain data proves integrity of what you anchored, not confidentiality.
