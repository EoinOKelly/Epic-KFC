# AI prompts — Eoin (cryptography & blockchain)

Prompt log for Cursor sessions on the **cryptography** module, **blockchain integrity** module, **backend/crypto integration**, and **team VM deployment**. Commit-only or empty follow-ups omitted.

---

## 1. Cryptography

### Initial module

> I need to build the standalone Cryptography module for our secure messaging app — utility functions my teammates can import into their clients and backend.
>
> Create a TypeScript/Node.js module (e.g. `cryptoEngine.ts`) using vetted libraries (`libsodium-wrappers` or Node `crypto`) that implements:
>
> 1. `hashPassword(password)` — Argon2id; return hash and salt  
> 2. `deriveKeys(masterKey, salt)` — HKDF for sub-keys (local storage, session)  
> 3. `encryptMessage(plaintext, symmetricKey)` — AES-256-GCM with auth tag and IV  
> 4. `decryptMessage(ciphertext, iv, authTag, symmetricKey)` — AEAD decrypt  
> 5. `generateKeyPair()` — asymmetric keypair for HPKE/TOFU  
> 6. `encryptPrivateKeyForStorage(privateKey, storageKey)` — private key at rest  
>
> Add inline comments on parameter choices (Argon2id memory limits, AEAD choice) so I can justify them in the cryptographic design document.
>
> Constraints: no custom primitives; use standard algorithms only; keep the API small and importable.

### Signal Protocol and brief

> I want to use the Signal Protocol because I believe that is the industry standard for secure messaging (see project brief and [Signal Protocol](https://en.wikipedia.org/wiki/Signal_Protocol)).
>
> Does Signal use AES-256-GCM? Implement encryption along the same lines where it fits our brief, and call out anything we do differently and why.

### Code walkthrough and concepts

> Explain what each file in the cryptography package does. Remove unnecessary code and comments where they do not help understanding.
>
> What does the “X” in X3DH stand for, and how does the double ratchet fit our architecture?

### Security review (lecturer-facing)

> Is the cryptography layer overcomplicated? In any path am I rolling my own crypto when I should call a maintained library instead?
>
> Fix anything that is bad practice. I need to justify every choice in the viva. List what my teammate must store in the database for keys, pre-keys, and ciphertext.
>
> Flag anything a lecturer might challenge — algorithm choice, post-quantum claims, nonce strategy, TOFU/key pinning, wire format. Explain how this module connects to the Python backend and the C++ client and where each step runs.

### Standard libraries (libsignal)

> For this project: if a standard library exists for a security primitive, use it.
>
> Refactor session setup and ratcheting to `@signalapp/libsignal-client` (or a maintained TypeScript port). Keep our package for Argon2/HKDF, at-rest GCM, wire format + DB types, and TOFU helpers.
>
> Why is this better than the previous approach? Any downsides for backend or client integration?

### Brief compliance — AEAD / GCM

> As far as I know you should always use a library rather than rolling crypto yourself. I noticed CBC+HMAC in places — the brief expects AEAD (GCM), not generic encrypt-then-MAC. Do not diverge from the brief; fix anything that does.

### Backend integration (step-by-step)

> I just pulled the full server backend. Combine my crypto code with the backend **slowly** — verify each step before the next. It is essential that I understand every hook.
>
> When I run the Signal smoke test, what actually happens? Add logging if useful (encrypted/decrypted, session steps). Is the crypto implementation strong enough to wire into production paths, or are there gaps first?
>
> I want to **see** messages encrypt and decrypt in tests if possible — does that exist already or do we need a small demo path?
>
> Review post-quantum considerations (e.g. whether “double the bit length” applies to X25519 vs AES). Should TOFU be in my TypeScript package or in the backend?
>
> My teammate is building the C++ client. **For now** only integrate crypto into the backend at the right call sites. Small diffs I can review — not one huge change.
>
> What was the purpose of the crypto layer **before** integration vs **after**? Will the backend run my TypeScript at runtime or only Python wrappers?
>
> How does my work link to teammate 1’s backend and teammate 2’s future client? Was TypeScript the right choice? What can I verify locally without Postgres if Daniel will test the DB on the VM?
>
> Is the `cryptography/` folder just a reference for the Python code? Daniel asked if I checked his **key endpoints** — what should I verify on `/api/v1/...` for identity keys and bundles?
>
> Are we still using the double ratchet end-to-end, or only static/pre-key flows?
>
> The client is separate C++. Is any TypeScript executed in production, or only at build/test time? What does `e2e-with-backend` prove? Can Daniel mirror that flow in C++?
>
> Walk through `e2e-with-backend` and the integrated backend path so I can explain it in the interview.
>
> Review `common.py` changes — were they all correct? Why `wire_payloads` and the “wire” naming? Was removing a missing-keys check acceptable?

### Architecture — role of the `cryptography/` folder

> What is the purpose of the `cryptography/` folder — reference implementation, npm package for scripts, or runtime dependency? Could we delete it without breaking the backend?

### Time trade-off (Postgres locally)

> How long to get Postgres working on my Windows machine — am I better spending ~30 minutes on that or on blockchain work, given Daniel can test DB on the VM?

---

## 2. Blockchain

### Initial scaffold

> I need to build the Blockchain integrity module for our secure messaging app.
>
> Scaffold a Hardhat project with:
>
> 1. `MessageFidelity.sol` — map conversation/message ID to `keccak256` hash and block timestamp; functions to store and retrieve a hash  
> 2. Deployment script for Ethereum Sepolia (ethers.js or viem)  
> 3. Standalone verification UI: user pastes message text, computes keccak256 locally, fetches on-chain hash, shows Pass/Fail  
>
> Keep the contract simple, gas-efficient, and commented only where non-obvious.

### Status and brief alignment

> What is the current status of the blockchain module — what is done, what is missing, and how does it align with the rest of the repo (backend anchors, crypto wire format)?
>
> Read the brief again against the code: what can stay, what must change for a working integrity layer that stores evidence of message history?

### Merkle design and mental model

> I own crypto and blockchain and need a realistic order of work. When a message is sent: keccak256 digest, anchor on Sepolia, optional Merkle path for verification — explain the flow in plain language and estimated effort.
>
> Is my job to expose something the backend calls on send (hash + on-chain record), not an NFT? Correct my mental model against the brief.
>
> Can we use a Merkle tree so new message hashes are appended but verifiers only need one root hash on-chain?
>
> Implement the Merkle tree design, then give a short file-by-file guide and what I must do next (env, deploy, teammate handoff).

### Deploy, test, and economics

> Trim comment noise — keep only comments that help a teammate understand the contract.
>
> What does “message fidelity” mean here (not the financial company)? I have one Sepolia wallet with ~0.05 ETH — step-by-step: compile, deploy, verify on Etherscan, run the standalone UI.
>
> One wallet or two (deployer vs worker that submits `storeHash`)?
>
> After deploy, when `anchor` / `storeHash` runs, what exactly is stored on-chain? How do I test from Hardhat console or the verification page? Explain the contract state model.
>
> Confirm we use **keccak256** for digests everywhere (off-chain and Solidity). Is the contract already deployed and callable, or only local?

### Hosting and teammate integration

> One Merkle tree per conversation or one global tree? What has to run on our **VM** vs what only needs Sepolia + Alchemy?
>
> What is `MESSAGE_FIDELITY_ADDRESS` for — who reads it (backend worker, scripts)? Does a `.env` in `blockchain/` mean every client must run Hardhat locally?
>
> Explain **Alchemy** (RPC) vs **deployer private key** vs **contract address**. I want a one-page handoff: function names, arguments, caller (backend worker / script), and nothing else teammates must run if the contract is already on Sepolia.
>
> Daniel asked whether blockchain should be “hosted on the VM”. What would actually run on the VM — only the Python worker and API, not the chain itself? Answer simply.
>
> What does the call chain look like end-to-end — does the `blockchain/` folder need `npm run build` before the backend worker can submit txs?

### Daniel’s anchor flow

> Daniel proposed:
>
> - Client → `POST /api/v1/messages` → backend stores message + **pending** anchor  
> - Blockchain worker → reads pending anchors → `storeHash(record_id, digest)` on Sepolia → saves `transaction_hash` → status **confirmed**  
> - Client → `GET /api/v1/messages/{message_id}/anchor` → show pending/confirmed  
>
> What is the blockchain worker? Do we already have one in `server/backend`? What do I need to implement vs what Daniel owns?

### Contract access control (integrity fix)

> Security review: `MessageFidelity.sol` allows **any** wallet to call `storeHash(recordId, contentHash)` and allows **overwriting** an existing `recordId`. That breaks tamper-evidence.
>
> Fix for the assignment:
> - Restrict `storeHash` to an owner/worker role  
> - Reject writes when `recordId` already exists  
> - Update Hardhat tests  
> - Say whether we must **redeploy** on Sepolia and what to change on the VM (`MESSAGE_FIDELITY_ADDRESS`, worker key)  
>
> After the fix, is behaviour the same for honest use, just with tighter write access?

### VM — redeploy, `.env`, worker failures

> Search prior sessions for how we redeployed the contract; give exact steps again.
>
> I need to find the backend `.env` on the VM and update the fidelity contract address after redeploy.
>
> Does the **deployer private key** change, or only `MESSAGE_FIDELITY_ADDRESS`?
>
> `sudo systemctl restart epic-messaging-blockchain-worker` then anchors fail — pasted `journalctl` from `blockchain_worker.py`. Diagnose (RPC, gas, nonce, wrong address, ABI mismatch) and fix without breaking crypto routes.

---

## 3. Backend / VM / Docker

### Docker and Postgres on the team VM

> Why was `docker-compose.yml` suggested? I know Docker can run Postgres — is Docker “the server”, or does the image have to run on the Alderaan VM?
>
> Daniel already has Postgres in Docker on the VM (`docker ps` shows `postgres:16` on port 5432). Remove my duplicate Docker setup and help me run the **FastAPI backend** against that database.
>
> I undid my Docker files; Postgres is up. Help me from current VM state: clone/pull repo, venv, `.env`, migrations, run API — step by step.
>
> Only create tables/migrations if you are sure Daniel has not already applied them.

### Verify deployment and 24/7 service

> Should backend + DB both be running on the VM now? Point my E2E/crypto tests at the hosted base URL instead of `localhost:8000`.
>
> The VM is a **long-term server** — the API must stay up 24/7, not die when I close SSH. Set up **systemd** (or equivalent), enable on boot, and tell me how to check status and logs.

### Team VM details and ports

> Our environment:
> - VM name: `kfc`  
> - IP: `200.69.13.70`  
> - SSH: port `2210`, user `student`  
>
> Clarify: SSH port `2210` is for shell access; HTTP API is port `8000` (or behind reverse proxy). Do not confuse them in curl examples.

### E2E from a developer laptop

> E2E tests should run **on my machine** against a **public API URL** on the VM — I should not need SSH open to run pytest/scripts.
>
> After systemd deploy, what URL should `curl` and my tests use for OpenAPI — `http://200.69.13.70:8000/docs` or a team hostname?

### External access and Networks module

> From Windows, `curl http://200.69.13.70:8000/docs` returns connection failed. SSH from WSL works with `ssh -p 2210 student@200.69.13.70`. What blocks external HTTP — firewall, bind address, missing reverse proxy?
>
> This counts toward the **Networks** part of the module. Suggest concrete checks on the VM (`ss -tlnp`, nginx, uvicorn `--host`) and fixes that do not weaken security.
>
> Our team name is **KFC** — there are multiple teams on shared infrastructure. Should the public URL include `kfc` (e.g. `https://kfc.theburkenator.com/docs`)?

### Shared infrastructure topology

> Is `200.69.13.70` unique to team KFC, or shared? Could another team also use port `8000`?
>
> KFC lives on a host called **Alderaan** — is KFC a separate VM or a container? Map what runs where: Postgres container, uvicorn, nginx, blockchain worker.
>
> If I close my WSL/SSH window, does the API keep running after systemd is configured?

### Local dev vs VM

> I want backend + DB working for local dev. Daniel said “DB is on Docker and already running” on the VM — explain how local `.env` differs from VM `.env` and what I should not duplicate.
>
> From terminal output on Windows: explain what command I was trying to run, why it failed (venv, path, wrong host), and fix with minimal changes.

### SSH access

> Go through my earlier chats and document how I have been SSHing into the VM (WSL, key path, port).
>
> `ssh -p 2210 student@200.69.13.70` → `Permission denied (publickey)` from one environment but works from WSL — what key and config should I use?

---

## 4. Teammate / repository

> Review `Epic-KFC-daniel-backend-db.zip` against my cryptography and blockchain work — what aligns, what conflicts, what breaks E2E anchors or key upload.
>
> Put the review in markdown I can share with Daniel, then rewrite it as a **integration guide** for my crypto package (endpoints, payloads, env vars).
>
> Initialise / connect remote `https://github.com/EoinOKelly/Epic-KFC.git` with sensible `.gitignore` for secrets and build artefacts.
>
> Review the whole repo for consistency — crypto, blockchain worker env, VM deploy scripts, and integration tests still match the current API.

---

## 5. Cross-cutting (quality and repo health)

> Review uncommitted changes in context of the full repo — anything outdated, broken imports, or docs that contradict the code?
>
> Complete the **root README** for the whole project (short, examiner-friendly): what each top-level folder does and how to run crypto tests, blockchain verify UI, and VM API smoke checks. *(Not the cryptographic design report — system overview only.)*

---

## Outcomes

| Area | What came out of it |
|------|---------------------|
| Cryptography | `cryptography/` package, libsignal ratchet, Argon2/HKDF/GCM, wire payloads, `e2e-with-backend`, Python `app/crypto` integration |
| Blockchain | Hardhat + Merkle `MessageFidelity`, Sepolia deploy, standalone verify UI, restricted `storeHash`, TS SDK for digests |
| Backend / VM | FastAPI on KFC VM, Postgres via existing Docker, systemd units, public docs URL, blockchain worker on VM |
| Integration | Shared guide for Daniel (keys, anchors, env), branch review notes, E2E against hosted API |
| Networks | Diagnosed SSH vs HTTP, team hostname, 24/7 service vs interactive SSH |

---

## Scope note (interview)

I used structured prompts for **planning and integration** (brief constraints, step-by-step VM deploy, security fix on `storeHash`), then validated with tests and teammate handoff docs. Cryptographic **design narrative** was written separately; this file is the engineering prompt log only.

*June 2026.*
