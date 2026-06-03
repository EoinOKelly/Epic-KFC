# Epic Messaging project documentation

CS4455 secure messaging app. This folder holds **cross-cutting** submission evidence; crypto design detail lives under `cryptography/docs/`, backend/network evidence under `server/docs/`.

| Document | Audience | Contents |
|----------|----------|----------|
| [Cryptographic-Design-kfc.docx](./Cryptographic-Design-kfc.docx) | Submission / crypto minor | **Canonical** crypto design (Word); regenerate with `python docs/scripts/build_crypto_design_docx.py` |
| [../cryptography/docs/security/cryptography.md](../cryptography/docs/security/cryptography.md) | Crypto, backend, clients | Markdown crypto design + implementation notes |
| [../cryptography/docs/security/threat-model.md](../cryptography/docs/security/threat-model.md) | Crypto, interview prep | Attacker classes A–D, guarantees, limits |
| [network_docs/network_deployment_threat_model.pdf](./network_docs/network_deployment_threat_model.pdf) | Networks minor | Deployment and edge threat model |
| [network_docs/network_architecture.pdf](./network_docs/network_architecture.pdf) | Networks minor | Network architecture diagram |
| [security/vulnerability_report.md](./security/vulnerability_report.md) | All minors | **Canonical** full-project vulnerability report |
| [security/penetration_testing_plan.md](./security/penetration_testing_plan.md) | Security review | Integrated pentest scope |
| [security/README.md](./security/README.md) | Security review | Index for project-wide security docs |
| [AI_Prompts/eoin_AI_PROMPTS.md](./AI_Prompts/eoin_AI_PROMPTS.md) | Crypto / AI artefact | AI prompt log (crypto, blockchain, VM, submission) |
| [blockchain/README.md](./blockchain/README.md) | Blockchain minor | Index for Sepolia integrity docs |
| [blockchain/blockchain-design.md](./blockchain/blockchain-design.md) | Blockchain minor | Design summary: hashing, anchoring, verification |

**Backend / DB (PDFs):** [server/docs/api/api_contract.pdf](../server/docs/api/api_contract.pdf), [server/docs/database/database_design.pdf](../server/docs/database/database_design.pdf), [server/docs/architecture/backend_architecture.pdf](../server/docs/architecture/backend_architecture.pdf).

**Examiner entry point:** [../README.md](../README.md) — whole-system map, quick start, and full documentation table.

## Repo layout

```
Epic Messaging/
├── client/              # C++20/Qt console client (TLS + native E2EE usage)
├── cryptography/        # npm package + docs/security (crypto design)
├── server/
│   ├── backend/         # FastAPI relay, PostgreSQL, blockchain worker
│   └── docs/            # API contract, architecture, security PDFs
├── blockchain/          # Solidity + Sepolia + fidelity verification UI
├── docs/                # this folder (crypto, blockchain, network PDFs, security)
└── README.md            # start here
```

## Build cryptography package

```bash
cd cryptography
npm install
npm run build
```

Import from Node/TS: `@epic-messaging/cryptography` or `../cryptography/dist`.
