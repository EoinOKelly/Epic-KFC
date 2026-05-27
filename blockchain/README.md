# Blockchain integrity module (Sepolia)

Tamper-evident anchoring of **keccak256** message/conversation digests via `MessageFidelity.sol`.

## Quick start

```bash
cd blockchain
npm install
cp .env.example .env
# Edit .env: SEPOLIA_RPC_URL, DEPLOYER_PRIVATE_KEY (Sepolia test ETH only)

npm run compile
npm test
npm run deploy:sepolia
```

After deploy, open the fidelity checker:

```bash
npm run serve:fidelity
# http://localhost:5173
```

Paste `fidelity-ui/deployment.json` values into the UI (or load from file if served locally).

## Integration for backend / client teams

| Function | Purpose |
|----------|---------|
| `storeHash(bytes32 recordId, bytes32 contentHash)` | Anchor a digest on-chain |
| `getHash(bytes32 recordId)` | Read digest + `anchoredAt` timestamp |
| `hasRecord(bytes32 recordId)` | Check existence without revert |

**Record ID convention:** derive a stable `bytes32`, e.g. `keccak256(utf8Bytes("conversation:" + id))` — the fidelity UI uses the same rule when you enter a conversation/message label.

**Content hash:** `keccak256` of the canonical payload bytes your crypto module produces (plaintext demo UI hashes UTF-8 message text).

## Project layout

```
blockchain/
  contracts/MessageFidelity.sol   # On-chain anchor
  scripts/deploy.ts             # Sepolia deploy + ABI export
  fidelity-ui/                  # Standalone Pass/Fail checker
  test/                         # Hardhat tests
```
