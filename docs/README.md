# Epic Messaging — project documentation

CS4455 secure messaging app. This folder is the shared reference for all teams.

| Document | Audience | Contents |
|----------|----------|----------|
| [architecture.md](./architecture.md) | Everyone | System diagram, modules, data flow |
| [cryptography.md](./cryptography.md) | Crypto, backend, clients | Algorithms, Signal flow, API surface |
| [database.md](./database.md) | Backend / DB | Tables, columns, what never goes on server |
| [backend-crypto-integration.md](./backend-crypto-integration.md) | Backend | Schema, API, and wiring to `cryptography/` |
| [integration.md](./integration.md) | All devs | How each minor connects to `cryptography/` |
| [threat-model.md](./threat-model.md) | Crypto, interview prep | Attackers, guarantees, limitations |
| [interview-prep.md](./interview-prep.md) | Crypto lead | Likely viva questions and short answers |

## Repo layout

```
Epic Messaging/
├── cryptography/     # npm package: passwords, E2EE (X3DH + ratchet), wire format
├── blockchain/       # Solidity + Sepolia + fidelity verification UI
├── docs/             # this folder
└── (backend, C++ client — add paths when present)
```

## Build cryptography package

```bash
cd cryptography
npm install
npm run build
```

Import from Node/TS: `@epic-messaging/cryptography` or `../cryptography/dist`.
