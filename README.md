# Epic Messaging (CS4455)

Team **kfc** — secure messaging for the Cybersecurity Epic Project 2026.

End-to-end encrypted 1:1 chat over a TLS API, with optional Sepolia anchors for conversation integrity. The server relays ciphertext and metadata only; it does not hold message plaintext or private keys.

## What is in this repo

| Area | Role |
|------|------|
| [cryptography/](./cryptography/) | Node/TS: passwords, Signal-style E2EE, wire format |
| [blockchain/](./blockchain/) | Solidity contract, Sepolia deploy, fidelity verification UI |
| [client/](./client/) | C++20/Qt console client (TLS to API, local crypto) |
| [server/backend/](./server/backend/) | FastAPI relay, auth, prekeys, audit, anchor jobs |
| [docs/](./docs/) | Architecture, threat model, integration, AI prompts |

## Quick start

Each module has its own README. Typical local order:

1. **Cryptography** — `cd cryptography && npm install && npm run build`
2. **Backend** — see [server/backend/README.md](./server/backend/README.md) (PostgreSQL, `.env`, migrations, `uvicorn`)
3. **Client** — see [client/README.md](./client/README.md) (CMake, Qt, OpenSSL)
4. **Blockchain** — see [blockchain/README.md](./blockchain/README.md) (`npm install`, tests, Sepolia deploy, fidelity UI)

Smoke checks (no full stack required):

```bash
cd cryptography && npm run smoke:signal
cd blockchain && npm test
```

Deployed API (TLS): `https://kfc.theburkenator.com/api/v1` — OpenAPI at `/docs` on that host.

## Documentation

Full design notes, database schema, backend–crypto wiring, and interview prep: **[docs/README.md](./docs/README.md)**
