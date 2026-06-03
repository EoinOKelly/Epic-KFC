# Epic Messaging project documentation

CS4455 secure messaging app. This folder is the shared reference for all teams.

| Document | Audience | Contents |
|----------|----------|----------|
| [architecture.md](./architecture.md) | Everyone | System diagram, modules, data flow |
| [Cryptographic-Design-kfc.docx](./Cryptographic-Design-kfc.docx) | Submission / crypto minor | **Canonical** crypto design doc (regenerate with `python docs/scripts/build_crypto_design_docx.py`) |
| [network_deployment_threat_model.pdf](./network_deployment_threat_model.pdf) | Networks minor (Burkley) | Separate from crypto; deployment and network threat model |
| [cryptography.md](./cryptography.md) | Crypto, backend, clients | Markdown copy of design + implementation notes |
| [database.md](./database.md) | Backend / DB | Tables, columns, what never goes on server |
| [backend-crypto-integration.md](./backend-crypto-integration.md) | Backend | Schema, API, and wiring to `cryptography/` |
| [integration.md](./integration.md) | All devs | How each minor connects to `cryptography/` |
| [threat-model.md](./threat-model.md) | Crypto, interview prep | Attackers, guarantees, limitations |
| [interview-prep.md](./interview-prep.md) | Crypto lead | Likely viva questions and short answers |
| [AI_PROMPTS.md](./AI_PROMPTS.md) | Module leads / report | Key AI prompts used during development |
| [security/vulnerability_report.md](./security/vulnerability_report.md) | Submission / all minors | **Canonical** vulnerability assessment (backend, crypto, client, blockchain) |
| [security/README.md](./security/README.md) | Security review | Index for project-wide security docs |

## Repo layout

```
Epic Messaging/
├── client/           # C++20/Qt console client (TLS + native E2EE usage)
├── cryptography/     # npm package: passwords, E2EE (X3DH + ratchet), wire format
├── server/
│   ├── backend/      # FastAPI relay, PostgreSQL, blockchain worker
│   └── docs/         # API contract, backend architecture, security evidence
├── blockchain/       # Solidity + Sepolia + fidelity verification UI
├── docs/             # this folder (cross-cutting design)
└── README.md         # examiner entry point — whole-system map
```

## Build cryptography package

```bash
cd cryptography
npm install
npm run build
```

Import from Node/TS: `@epic-messaging/cryptography` or `../cryptography/dist`.
