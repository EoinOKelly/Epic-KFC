# Server Documentation Index

Backend setup and run instructions live in:

```text
backend/README.md
```

Core backend documentation:

- `docs/architecture/backend_architecture.md`
- `docs/architecture/network_architecture.md`
- `docs/api/api_contract.md`
- `docs/database/database_design.md`
- `docs/deployment/runbook.md`
- `docs/security/security_controls_mapping.md`
- `docs/security/threat_model.md`
- `docs/security/network_deployment_threat_model.md`
- `docs/security/penetration_testing_plan.md`
- `docs/security/security_test_results.md`
- `docs/security/vulnerability_report.md`

Blockchain anchor behavior is documented in the API contract, backend architecture, database design, operations runbook, and security reports. FastAPI creates pending anchor rows for sent/forwarded messages, while the backend blockchain worker submits those rows to Sepolia.

AI artefacts:

- `docs/ai/backend_prompts_daniel.md` contains the sanitised backend/database prompt log.
