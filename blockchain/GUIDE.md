# Blockchain module

## What "fidelity" means

Not the investment company. **Message fidelity** means: does the content you have now hash to the same value we stored on-chain? Pass means the digest matches. Fail means wrong text, wrong message id, or a missing anchor.

The `fidelity-ui/` folder is a standalone page for that check. It does not need the messaging app running.

---

## Design (CS4455 blockchain brief)

### On-chain vs off-chain

| On-chain (Sepolia) | Off-chain (app / DB) |
|--------------------|----------------------|
| Merkle root of a conversation (`bytes32`) | Message plaintext |
| `recordId` (conversation label) | Full message list for proof rebuild |
| Block timestamp when anchored | Transaction hash in `blockchain_anchors` |

Plaintext never goes to the contract. Anyone can read hashes on Etherscan; that is expected for integrity proofs.

### Why keccak256

Ethereum tooling and Solidity use **keccak256** as the standard 32-byte hash. Our leaves hash `(messageId, keccak256(plaintext))` in TypeScript and verify with the same rule in `MessageFidelity.sol`. Using SHA-256 on-chain would need extra encoding and would not match native EVM helpers.

### Merkle root instead of one tx per message

The brief allows anchoring a **conversation segment** rather than every single message. We sort messages by `createdAt` then `messageId`, build a binary Merkle tree, and store **one root** per segment via `storeHash(recordId, merkleRoot)`.

Benefits: lower gas, one anchor covers many messages. Trade-off: to verify one message you need the full ordered list (or a stored proof) off-chain.

When a conversation grows, anchor a **new** `recordId` (segment), not the previous one. TypeScript derives segment ids with `deriveConversationSegmentRecordId(userA, userB, segmentKey)`. Default `segmentKey` is the message count in the batch being anchored.

### Write control and immutability

`MessageFidelity.sol` restricts `storeHash` to the contract **owner** (the deployer address set in the constructor). Each `recordId` is **write-once**: a second `storeHash` for the same id reverts with `RecordAlreadyAnchored`. That supports tamper-evidence: the chain record is the first anchored digest for that id, not whatever wallet wrote last.

Only the wallet whose private key matches `owner` should submit anchors (typically `DEPLOYER_PRIVATE_KEY` in `blockchain/.env`, or a dedicated backend worker wallet if you redeploy with that address as deployer).

### Gas

Each `storeHash` is a state-changing transaction on Sepolia testnet. Cost depends on network congestion; test ETH from a faucet is enough for demos. Once mined, the stored root and timestamp are fixed for that `recordId`.

### Deployed contract (team kfc)

| Field | Value |
|-------|--------|
| Network | Sepolia (`chainId` 11155111) |
| Address | `0x69d3D7D9E50141faef9AC957D6450a4ccb37c404` |
| ABI | `fidelity-ui/MessageFidelity.abi.json` (also exported from Hardhat artifacts) |
| Metadata | `fidelity-ui/deployment.json` |
| On-chain behaviour (this address) | **Demo-only:** unrestricted `storeHash` and overwrites (pre-hardening deployment) |
| Source behaviour (redeploy required) | Owner-only `storeHash`, write-once per `recordId` |

Etherscan: `https://sepolia.etherscan.io/address/0x69d3D7D9E50141faef9AC957D6450a4ccb37c404`

Redeploy after pulling hardened Solidity, then update `.env`, `fidelity-ui/deployment.json`, and any backend worker `MESSAGE_FIDELITY_ADDRESS`. Until then, treat Sepolia verification as demonstrating the flow, not production-grade anchor immutability.

---

## Setup and deploy

### 1. RPC URL

Create an app on [Alchemy](https://www.alchemy.com/) or [Infura](https://infura.io/) for **Sepolia** and copy the HTTPS endpoint.

### 2. Wallet key (testnet only)

In MetaMask: Account menu, account details, export private key. Starts with `0x`. Never commit this file. Never use mainnet keys for class work.

### 3. `blockchain/.env`

```env
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
DEPLOYER_PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE
MESSAGE_FIDELITY_ADDRESS=0x69d3D7D9E50141faef9AC957D6450a4ccb37c404
```

Redeploy only if you need your own contract:

```powershell
cd "c:\Users\eoino\Year2\Epic Messaging\blockchain"
npm install
npm run compile
npm run deploy:sepolia
```

Copy the printed address into `.env` and `fidelity-ui/deployment.json`.

### 4. Build TypeScript API

```powershell
npm run build
```

---

## Run the demo

Terminal 1 (backend, if needed):

```powershell
cd server\backend
uvicorn app.main:app --reload
```

Terminal 2:

```powershell
cd cryptography
npm run build

cd ..\blockchain
npm run build
npm run e2e
```

That path registers users, sends E2EE messages through the API, builds the Merkle tree, anchors on Sepolia, and verifies one leaf.

Merkle math only (no chain):

```powershell
$env:SKIP_BLOCKCHAIN="1"; npm run e2e
```

---

## Verification page

```powershell
npm run serve:fidelity
```

Open http://localhost:5173. Load `deployment.json`, enter RPC URL, both user UUIDs, the messages JSON array, and the message id to check. The page recomputes the leaf, fetches the on-chain root, runs `verifyMessageInHistory`, and shows pass or fail with the anchor timestamp.

Message JSON shape (must match `anchorConversationOnChain`):

```json
[
  { "messageId": "uuid-1", "plaintext": "hello", "createdAt": "2026-01-01T00:00:00.000Z" }
]
```

`recordId` on chain is `ethers.id("direct:" + sortedUserA + ":" + sortedUserB)`.

---

## Integrator API

```javascript
const {
  anchorConversationOnChain,
  verifyMessageOnChain,
} = require("./dist/index");

await anchorConversationOnChain(aliceUserId, bobUserId, [
  { messageId: "...", plaintext: "...", createdAt: "..." },
]);

const { pass } = await verifyMessageOnChain(
  aliceUserId, bobUserId, messages, messageId
);
```

Store `chain.transactionHash` in your `blockchain_anchors` table for later lookups.

---

## File map

| File | Role |
|------|------|
| `contracts/MessageFidelity.sol` | `storeHash`, `getHash`, Merkle proof verify |
| `src/merkle.ts` | Leaf and tree hashing (matches Solidity) |
| `src/conversation.ts` | Order messages, derive segment `recordId` |
| `src/index.ts` | `anchorConversationOnChain`, `verifyMessageOnChain` |
| `scripts/deploy.ts` | Deploy to Sepolia |
| `scripts/e2e-with-backend.js` | End-to-end with crypto + API |
| `fidelity-ui/` | Browser verifier |

---

## Interview talking points

1. **Hash function:** keccak256 is the EVM native hash; leaves bind `messageId` to content hash.
2. **Transaction:** wallet signs `storeHash`; miners include it; receipt gives `transactionHash`.
3. **Gas:** paid in test ETH; larger trees off-chain mean the same on-chain cost (one root).
4. **Immutability:** historic blocks are hard to rewrite; you trust Ethereum consensus on Sepolia for demo integrity.
5. **Limits:** chain does not encrypt; wrong ordering of messages breaks proofs; anchoring is separate from E2EE.
