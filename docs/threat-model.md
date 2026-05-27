# Threat model

Aligned with CS4455 cryptography brief (four attacker classes).

## Attackers

| Class | Capability |
|-------|------------|
| **A. Passive network** | Read traffic client ↔ server |
| **B. Active network** | Modify, drop, replay, inject traffic |
| **C. Honest-but-curious server** | Follows protocol; logs ciphertext and metadata |
| **D. Compromised server** | Full DB + can send arbitrary API responses |

## What E2EE provides

| Property | A | B | C | D |
|----------|---|---|---|---|
| Message **confidentiality** (past ciphertext) | Yes | Yes | Yes | Yes* |
| **Integrity** of ciphertext (detect tamper) | — | Yes (GCM) | Yes | Yes |
| **Authenticity** of sender (cryptographic) | — | Partial** | Partial** | Partial** |
| Hide **metadata** (who/when) | No | No | No | No |
| **Forward secrecy** (after ratchet advance) | Yes | Yes | Yes | Yes† |
| Prevent server **dropping** messages | No | No | No | No |
| Prevent **MITM on first contact** without TOFU verify | No | No | No | No |

\*Assumes clients did not leak keys; server never had private keys.  
\**Via signed pre-keys + TOFU on identity; not a full PKI.  
†If long-term state on client is stolen, limited break-in recovery depends on ratchet step.

## Passwords vs message keys

- **Argon2id** protects the **account** if the DB leaks.
- **Message keys** come from X3DH/ratchet, not from the password.
- Local private keys should use `deriveKeys` + `encryptPrivateKeyForStorage` with a user passphrase (client responsibility).

## Deviations from Signal (document explicitly)

| Signal production | This project |
|-------------------|--------------|
| libsignal audited ratchet | In-repo ratchet + spec-based KDF |
| AES-CBC + HMAC payloads | AES-256-GCM (brief requirement) |
| PQXDH optional | Classical X25519 only |

## Blockchain

- On-chain hashes are **public** on Sepolia.
- Anchoring does not encrypt; it only supports **fidelity** (“this digest was recorded at time T”).
