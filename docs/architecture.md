# System architecture

## High-level view

```mermaid
flowchart TB
  subgraph clients [Clients]
    CPP[C++ client]
    WEB[Optional web client]
  end

  subgraph transport [Networks minor]
    TLS[TLS 1.2+ to server]
  end

  subgraph server [Backend]
    API[REST API]
    DB[(Database)]
    API --> DB
  end

  subgraph crypto_pkg [cryptography package]
    AUTH[Argon2id + HKDF]
    E2EE[X3DH + Double Ratchet + AES-256-GCM]
    AUTH --- E2EE
  end

  subgraph chain [Blockchain minor]
    DIGEST[keccak256 conversation digest]
    SEPOLIA[Sepolia MessageFidelity.sol]
    UI[fidelity-ui verifier]
    DIGEST --> SEPOLIA --> UI
  end

  CPP --> crypto_pkg
  WEB --> crypto_pkg
  CPP --> TLS --> API
  WEB --> TLS --> API
  CPP -.->|optional integrity anchor| DIGEST
```

## Security layers (do not merge in explanations)

| Layer | Protects against | Does *not* hide |
|-------|------------------|-----------------|
| **TLS** | Network eavesdropping/tampering on the wire to your VM | Content from the server operator |
| **E2EE** (`cryptography/signal`) | Server reading or forging message plaintext | Metadata (who, when, sizes), ciphertext blobs |
| **Blockchain digest** | Undetected change to an anchored conversation hash | Message content (hash is public on Sepolia) |

## End-to-end message flow

```mermaid
sequenceDiagram
  participant A as Alice client
  participant S as Backend
  participant B as Bob client

  A->>S: Login (password verify, TLS)
  B->>S: Login
  B->>S: Upload pre-key bundle (public keys only)
  A->>S: GET Bob pre-key bundle
  Note over A: createInitiatorSession + signalEncrypt
  A->>S: POST wire_payload_json (ciphertext)
  S->>B: Deliver message (poll/push)
  Note over B: deserializeWireMessage + signalDecrypt
  B-->>B: Plaintext in UI
```

## Module ownership (CS4455)

| Minor | Owner focus | Repo path |
|-------|-------------|-----------|
| Cryptography | E2EE, passwords, key derivation, TOFU | `cryptography/` |
| Blockchain | On-chain digest + verification UI | `blockchain/` |
| Networks | TLS, server hardening, pentest | Backend + deployment |
| C++ | Client UI, local store, crypto *usage* | TBD |
