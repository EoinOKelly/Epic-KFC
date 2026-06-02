# AI Prompts — Epic Messaging (CS4455)

This document records the main prompts used with Cursor/AI assistants while building the **cryptography**, **blockchain integrity**, and **backend deployment** parts of the project. Trivial prompts (commit messages, one-word checks, empty follow-ups) are omitted.

Prompts are grouped by module. Wording has been lightly edited for clarity where the original was informal; intent is unchanged.

---

## 1. Cryptography module

### 1.1 Initial scaffold (design document alignment)

> I need to build the standalone Cryptography module for our secure messaging app — a set of utility functions my teammates can import into their clients and backend.
>
> Please create a TypeScript/Node.js module (e.g. `cryptoEngine.ts`) using standard, vetted libraries (e.g. `libsodium-wrappers` or Node’s native `crypto`) that implements:
>
> 1. `hashPassword(password)` — Argon2id; return hash and salt  
> 2. `deriveKeys(masterKey, salt)` — HKDF to derive sub-keys (local storage, session)  
> 3. `encryptMessage(plaintext, symmetricKey)` — AES-256-GCM with auth tag and IV  
> 4. `decryptMessage(ciphertext, iv, authTag, symmetricKey)` — AEAD decrypt  
> 5. `generateKeyPair()` — asymmetric keypair suitable for HPKE/TOFU  
> 6. `encryptPrivateKeyForStorage(privateKey, storageKey)` — encrypt private key at rest  
>
> Add inline comments explaining parameter choices (especially Argon2id memory limits and AEAD choice) so I can justify them in my cryptographic design document.

### 1.2 Signal Protocol and brief compliance

> I want to align with the Signal Protocol (see project brief and [Signal Protocol](https://en.wikipedia.org/wiki/Signal_Protocol)). Does Signal use AES-256-GCM, and how should our encryption map to that model while staying quantum-resilient where the brief requires it?

### 1.3 Code quality and maintainability

> Explain what each file in the cryptography package does.

### 1.4 Conceptual understanding (for viva / design doc)

> What does the “X” in X3DH stand for, and how does the Double Ratchet work in our architecture?

### 1.5 Security review — avoid rolling your own crypto

> Is the cryptography layer overcomplicated? In any path am I effectively rolling my own crypto when I should call a well-maintained library instead? Fix anything that is bad practice so I can justify every choice to my lecturer. Also list what my teammate needs to store in the database.

### 1.6 Lecturer-facing audit

> Are there red flags a lecturer might challenge — e.g. lack of post-quantum claims, rolling custom crypto, weak rationale for algorithm choices? Explain how this module connects to the backend and C++ client, and where it sits in the end-to-end flow.

### 1.7 Project documentation

> Add a general documentation or wiki area (diagrams, integration notes) anywhere it fits the repo structure.

### 1.8 Standard libraries over custom implementations

> For this project, if a standard library exists for a security primitive, use it. Refactor session setup and ratcheting to use `@signalapp/libsignal-client` (or a maintained TypeScript port), and keep our package focused on Argon2/HKDF, at-rest GCM, wire format, DB types, and TOFU helpers.

### 1.9 Brief compliance — AEAD only

> What is the best approach for crypto overall — always prefer libraries over custom implementations. I noticed CBC+HMAC in places; the brief requires AEAD (GCM). Do not diverge from the brief — fix anything that uses encrypt-then-MAC instead of GCM where the spec says otherwise.

### 1.10 End-to-end flow and git workflow

> Break down the full cryptographic flow as it stands now. I have pulled the server backend from main — help me combine my crypto code with the backend step by step, verifying each stage before moving on. It is essential that I understand each integration point.

### 1.11 Observability and confidence before integration

> When I run the Signal smoke test, what exactly happens step by step? Add log output where helpful (encrypted/decrypted, session state) so I can see the pipeline. Is this implementation industry-grade, or are there gaps I should fix before wiring it into the backend?

### 1.12 Post-quantum and TOFU ownership

> Review post-quantum considerations (e.g. whether doubling key sizes is appropriate for X25519 vs symmetric algorithms). Should TOFU be implemented in my TypeScript package or in the server backend?

### 1.13 Backend integration (incremental)

> A teammate is working on the C++ client. For now, wire my cryptography into the backend so it is invoked at the correct points. Make changes in small, reviewable steps rather than one large diff.

### 1.14 Architecture clarity (TS vs Python vs C++)

> Explain the purpose of the TypeScript crypto package versus the Python backend wrappers. How does it link to teammate 1’s backend and teammate 2’s future C++ client? Was TypeScript the right choice? What can I run locally to verify backend + crypto work together without Postgres if my teammate will test DB later?

### 1.15 Client integration reference

> The client is separate C++. Is any of my TypeScript executed at runtime today, or only via build/scripts? What does `e2e-with-backend` demonstrate — can my teammate use it as the reference for the C++ client (same steps, different language)? Walk through the relevant code paths.

### 1.16 Integration review — wire format and validation

> Review recent backend changes (e.g. `common.py`, wire payload validation). Were removing certain key checks safe? Explain the purpose of wire payloads and the “wire” naming in this project.

---

## 2. Blockchain integrity module

### 2.1 Initial scaffold

> I need to build the Blockchain integrity module for our secure messaging app.
>
> Scaffold a Hardhat (or Node.js) project with:
>
> 1. Solidity contract `MessageFidelity.sol` mapping conversation/message ID to `keccak256` hash and block timestamp; functions to store and retrieve a hash  
> 2. Deployment script for Sepolia testnet (ethers.js or viem)  
> 3. Standalone web UI (HTML/JS or simple React): paste message text, compute keccak256 locally, fetch on-chain hash, show green Pass / red Fail  
>
> Keep the contract simple, gas-efficient, and well-commented.

### 2.2 Gap analysis against brief and repo

> Review the project brief and existing codebase. What can stay as-is and what must change for a working blockchain that stores message history with integrity guarantees?

### 2.3 Conceptual model (Merkle, anchoring)

> I own crypto and blockchain and need a clear timeline. When a message is sent, should we keccak256-hash it and anchor evidence on-chain? Should a Merkle proof path exist for verification? Explain in plain terms — I am struggling to map the brief to implementation.

### 2.4 Integration responsibility

> Is my job to expose an API/function called when messages are sent that hashes the payload and records it on a smart contract (not necessarily an NFT)? Am I aligned with the brief or misunderstanding the role of on-chain storage?

### 2.5 Merkle tree design

> Can we use a Merkle tree so new message hashes are appended to the tree but verifiers only need a single root hash to prove all messages were anchored? Implement that design and provide a short guide: what each file does and what I need to do next (deploy, env, teammate handoff).

### 2.6 Deployment and terminology

> Trim excessive comments so the code looks human-maintained. What does “fidelity” mean in this module (not the financial company)? I have one Sepolia wallet with ~0.05 ETH — give step-by-step deploy and test instructions.

### 2.7 Operations model (per-chat tree, hosting, env)

> Is there one Merkle tree per chat or a global tree? How does hosting work — must this run on our VM, or is Sepolia enough? What should `MESSAGE_FIDELITY_ADDRESS` be set to after deploy? What backend work is required versus client-only verification?

### 2.8 Alchemy, keys, and teammate handoff

> Explain what Alchemy provides versus our deployer private key versus `MESSAGE_FIDELITY_ADDRESS`. I want a minimal integration guide: exported functions, arguments, and behaviour so backend/client teammates can call them without running our node process locally if the contract is already deployed.

### 2.9 Blockchain worker (team architecture)

> Teammate proposed this flow: client POSTs message → backend stores message and pending anchor → worker reads pending anchors → calls `storeHash` on-chain → updates anchor status → client polls anchor endpoint. What is the “blockchain worker”? Do we need one, and do we already have it?

---

## 3. Backend, database, and VM deployment

### 3.1 Docker and Postgres basics

> Why is `docker-compose.yml` needed? I know Docker provides a Postgres image — how does this fit together? Is Docker “the server”, or must the image run on the VM?

### 3.2 VM already has Postgres

> My teammate already runs Postgres in Docker on the VM. Remove redundant Docker setup from my branch and help me get the FastAPI backend running against that database.

### 3.3 Deploy backend on shared VM (initial state)

> Docker Postgres is already up on the VM. Help me deploy the rest of the backend API from my current shell state (paths, git layout, migrations, env).

### 3.4 Avoid duplicating schema work

> Only create database objects or migrations if you are certain my teammate has not already created them.

### 3.5 Verify VM deployment

> Should the backend and DB both be running on the VM now? Adapt my tests so I can confirm end-to-end against the hosted API.

### 3.6 Production-like VM (24/7 API)

> The VM is a long-term server — the API should run 24/7, not only while my SSH session is open. Set up a durable service (e.g. systemd) and tell me how to proceed.

### 3.7 E2E against hosted API

> Run the full E2E test against the backend hosted on the VM, not localhost.

### 3.8 Networking and team URL

> VM: `kfc`, IP `200.69.13.70`, SSH port `2210`, user `student`. Should API tests use port 2210 or 8000? E2E tests should run locally against a public API URL — the VM should expose HTTP, not require SSH to run tests. Our team hostname may include `KFC` (e.g. `https://kfc.theburkenator.com/docs`) — confirm the correct base URL and help debug connectivity from outside the VM.

### 3.9 Shared VM topology

> Is port 8000 unique to our team or shared across teams on Alderaan? Is `KFC` a dedicated sub-VM? Will the backend keep running if I close my WSL/SSH window?

### 3.10 Local backend + DB setup

> I want the backend and database working locally. Teammate said “the DB is on Docker and already running” — explain how that works and what I need before deploying to the VM.

### 3.11 Terminal errors — pytest / venv

> From my terminal output: explain what I was trying to run, what failed, and fix it without large unrelated changes.

---

## 4. Integration and teammate coordination

### 4.1 Review teammate’s backend branch

> Review `Epic-KFC-daniel-backend-db.zip` (teammate’s backend/DB branch). Compare it to my cryptography and blockchain work — what aligns well, what conflicts, and what should we merge or change?

### 4.2 Shareable integration guide

> Put the review findings into a markdown file I can share with my teammate, then rephrase it as a guide for integrating with my crypto module.

### 4.3 Repository initialisation

> Initialise this workspace with remote `https://github.com/EoinOKelly/Epic-KFC.git` (gitignore, first commit structure as appropriate).

---

## 5. How these prompts were used

| Area | Typical outcome |
|------|-----------------|
| Cryptography | `cryptography/` package, Signal/libsignal integration, wire format, `e2e-with-backend.js`, `docs/cryptography.md` |
| Blockchain | `blockchain/` Hardhat project, Merkle anchoring, Sepolia deploy, fidelity UI, TS SDK for anchors |
| Backend / VM | FastAPI on VM, systemd unit, team URL, integration with crypto validation |
| Integration | `docs/backend-crypto-integration.md`, teammate review notes |

---

*Generated for module documentation and demonstration of AI-assisted development. Last updated: June 2026.*
