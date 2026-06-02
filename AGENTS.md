# AGENTS.md

## Repository Purpose

This repository is for the CS4455 Cybersecurity Epic Project 2026 for team `kfc`.

The project is a secure messaging application. It must demonstrate confidentiality,
integrity, and authenticity of communications while incorporating all four assessed
areas:

- Computer Networks & Cybersecurity
- C++ Programming
- Cryptography
- Blockchain

The system should include a C++ client component, a backend service/API, end-to-end
encrypted messaging, secure client/server connectivity, and a blockchain-backed
message fidelity proof.

Keep solutions simple, demonstrable, and easy for every team member to explain in
the presentation and interview.

## Current Repository Layout

- `client/`: C++ client component, currently a Qt/CMake project.
- `cryptography/`: TypeScript cryptography utilities and protocol work.
- `blockchain/`: Hardhat/Solidity message fidelity contract, scripts, tests, and
  standalone verification UI.

## Core Deliverables

The repo should support these submission requirements:

- all source code needed to build and run the project
- a README with dependency, setup, build, and run instructions
- secure messaging functionality: sign-up/login, message send/receive, message
  listing, forwarding, revocation, download, and deletion where implemented
- C++ component that is meaningfully connected to the secure messaging app
- TLS-protected client/server connectivity with certificate validation
- end-to-end authenticated encryption for message payloads
- blockchain digest anchoring on Ethereum Sepolia
- standalone message verification page
- design notes, diagrams, testing evidence, deployment notes, and AI prompt
  artefacts needed for submission and interview defence

## Working Rules

- Prefer the simplest implementation that satisfies the assignment brief.
- Make small, scoped changes that are easy to review.
- Preserve existing behaviour unless the task requires a change.
- Do not introduce frameworks, services, or dependencies unless they clearly help
  satisfy the spec or integrate with another team component.
- Keep code readable enough for a second-year student team to explain.
- Use vetted libraries for cryptography and secure networking.
- Keep cryptography and blockchain code modular so the C++ client and backend/DB
  work can integrate with it cleanly.
- Validate meaningful changes before calling them complete.
- Record important AI-assisted decisions and corrections for the AI artefacts.
- Never invent test results, deployment evidence, prompt artefacts, or security
  claims.

## C++ Client Rules

The C++ work is worth 25% of the project. Treat `client/` as a first-class assessed
component, not a throwaway launcher.

Expected standards:

- Build a working C++ component related to the secure messaging app.
- Use CMake where possible and keep build instructions clear.
- Organise code across `.h`/`.hpp` and `.cpp` files when the component grows beyond
  a tiny skeleton.
- Use functions to break work into focused tasks.
- Use classes where they model real project concepts such as `User`, `Message`,
  `Conversation`, `Client`, or `MessageStore`.
- Use constructors, public/private access, and object ownership deliberately.
- Use inheritance or polymorphism only when it makes the design clearer.
- Prefer normal objects, references, STL containers, and RAII.
- Use `std::unique_ptr` or `std::shared_ptr` only when ownership semantics justify
  them, and be able to explain who owns each important object.
- Avoid owning raw pointers and manual `new`/`delete`.
- Use STL containers and algorithms where appropriate, such as `std::vector`,
  `std::map`, `std::set`, `std::unordered_map`, `std::find`, `std::sort`,
  `std::count`, and `std::copy`.
- Use `const`, references, lambdas, and modern C++ features where they improve
  clarity.
- Keep the C++ standard modern and portable. The current client target is C++20.

When adding networking to the C++ client:

- Use TLS for connections to the backend.
- Verify certificate authenticity and validity.
- Do not disable certificate verification to make demos easier.
- Handle connection failures, invalid responses, and authentication failures with
  clear user-facing messages.

## Team Integration Rules

The current project split is:

- blockchain and cryptography are this repo's strongest focus areas
- the C++ client and backend/database work may be handled by teammates
- code in `cryptography/` and `blockchain/` should expose clear interfaces that
  other project components can call

When building integration points:

- prefer small, documented functions, scripts, and data formats over tightly
  coupled code
- keep request/response shapes, digest formats, key formats, transaction hashes,
  and deployment metadata explicit
- avoid assumptions that only work inside one local demo setup
- document anything the C++ client or backend team must provide, such as public
  keys, message IDs, user IDs, ciphertext fields, digest inputs, or contract
  addresses

## Cryptography Rules

The cryptography work must provide end-to-end encrypted communication. The server
may relay ciphertext and store metadata, but it must not be able to read message
contents or undetectably tamper with them.

Mandatory principles:

- Use a standard AEAD scheme for message payloads, such as AES-256-GCM or
  ChaCha20-Poly1305.
- Do not use custom encryption constructions, Encrypt-and-MAC, MAC-then-Encrypt,
  ECB mode, DES, 3DES, RC4, MD5, SHA-1 in security roles, textbook RSA, hardcoded
  keys, hardcoded IVs, or nonce reuse.
- Use vetted libraries only, such as libsodium, OpenSSL EVP, Web Crypto,
  `cryptography`, PyCryptodome, `hpke-js`, or `pyhpke`.
- All randomness must come from a CSPRNG.
- Establish shared cryptographic state without revealing it to the server.
- Prefer HPKE Mode_Auth concepts using X25519/HKDF-SHA256 with a justified AEAD,
  unless a different vetted construction is explicitly justified.
- Recipients must be able to verify message origin.
- State and implement the public-key trust model. TOFU with key pinning is
  acceptable and expected unless a stronger model is designed.
- Use HKDF with explicit `salt` and `info` values for domain-separated key
  derivation.
- Use memory-hard server-side password hashing. Argon2id is preferred; PBKDF2-HMAC-
  SHA256 requires clear justification and strong parameters.
- Encrypt long-term private keys at rest under a separately derived local key.

Cryptographic design notes must explain:

- threat model for passive network attackers, active network attackers,
  honest-but-curious servers, and fully compromised servers
- which properties survive server compromise and which do not
- registration, key publication, send, receive, and local storage flows
- primitive choices and parameters with citations where relevant
- nonce strategy and consequences of nonce reuse
- limitations and trade-offs

Crypto implementation should be readable and should explain why security-sensitive
choices were made. Prefer concise comments near non-obvious cryptographic choices
and fuller rationale in design notes.

## Blockchain Rules

The blockchain work must provide tamper-evident integrity verification for messaging
data.

Expected behaviour:

- Write and maintain a Solidity smart contract that records `keccak256` message or
  conversation digest hashes with block timestamps.
- Deploy to Ethereum Sepolia.
- Provide the deployed contract address and ABI.
- When messages or conversation segments are anchored, compute the digest off-chain
  and submit the hash through a transaction.
- Store transaction hashes so records can be verified later.
- Consider gas and persistence trade-offs. Hashing every message may be excessive;
  conversation segment anchoring is acceptable if documented.
- Maintain an independent verification UI where a user can enter message content,
  retrieve on-chain hash/timestamp data, compare digests, and see a clear pass/fail
  result.

Students must be able to explain hash functions, why `keccak256` is used, Ethereum
transactions, gas costs, immutability, and on-chain versus off-chain data.

## Network And Backend Security Rules

The system must use secure connectivity between clients and backend services.

Required expectations:

- Use SSL/TLS for client/server communication.
- Clients must verify the backend certificate.
- Authenticate and authorise users securely.
- Validate inputs on both client and server where relevant.
- Protect against common issues such as broken authentication, broken access
  control, injection, cryptographic misuse, security misconfiguration, sensitive
  data exposure, and vulnerable components.
- Document network architecture, backend endpoints, database/external service
  connections, and deployment assumptions.
- Include penetration/vulnerability testing evidence where practical.

## Documentation And Traceability

This project is graded partly on explanation and AI-assisted development oversight.
Maintain useful traceability as work evolves.

For meaningful changes, update or create relevant docs such as:

- root or component README files
- design notes for cryptography, networking, blockchain, and C++ architecture
- deployment notes
- testing notes/checklists
- AI prompt artefact summaries
- contribution notes for the cover document

Record:

- what was requested
- design decisions made
- files changed
- security assumptions and limitations
- validation performed
- manual checks still required
- AI output that was accepted, modified, debugged, or rejected

Prefer concise human-authored summaries over generic AI commentary.

## Testing And Validation

Do not mark meaningful work complete without validation.

Use the validation path that matches the changed area:

- C++ client: configure/build with CMake, run the executable or relevant tests, and
  document any manual UI or CLI checks.
- Cryptography: run unit tests or small protocol checks for encryption,
  decryption, tamper rejection, key derivation, and error cases.
- Blockchain: run Hardhat tests, compile contracts, and document deployment or
  Sepolia verification steps when relevant.
- Verification UI: test valid and invalid hash comparisons and clear pass/fail
  display.
- Backend/networking: test authentication, authorisation, TLS behaviour, input
  validation, and error handling.

Always state exactly what commands were run and what remains unverified.

## Secrets And Sensitive Material

Never commit or paste sensitive material into source, docs, tests, logs, or AI
artefacts.

Do not commit:

- private keys
- seed phrases
- wallet exports
- real `.env` secrets
- deployment credentials
- API keys
- passwords
- database credentials
- real user secrets or private messages

Use placeholders in examples. If a secret appears in a diff or generated file, stop,
warn the user, remove or sanitise it, and do not proceed to commit until the diff is
clean.

## AI Artefact Rules

The submission must include AI prompt artefacts and students may be questioned about
them.

When AI helps with meaningful work:

- keep enough prompt/response evidence to discuss later
- note what was useful
- note what required correction
- identify any AI output that was rejected or debugged
- ensure every student can explain the final code regardless of who or what wrote
  the first draft

Do not submit AI-generated code that the team cannot explain.

## Definition Of Done

A task is done only when:

- the change matches the secure messaging project spec
- code is scoped, readable, and explainable
- relevant security requirements are handled or explicitly documented as out of
  scope
- validation has been run where practical
- docs or AI traceability notes are updated when the change is meaningful
- the final response states files changed, commands run, validation outcome, and
  remaining risks or manual checks

## Do Not Rules

- Do not hand-roll cryptographic primitives.
- Do not disable TLS or certificate checks for convenience.
- Do not store plaintext passwords or unencrypted long-term private keys.
- Do not use placeholder security logic for core behaviours.
- Do not broaden refactors beyond the requested task.
- Do not add unnecessary packages or services.
- Do not fabricate evidence, deployment results, tests, or AI artefacts.
- Do not commit secrets.
