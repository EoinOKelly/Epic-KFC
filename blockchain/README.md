# Blockchain (message integrity on Sepolia)

Merkle-root anchoring for conversation digests. Plaintext stays off-chain; Sepolia stores a `keccak256` root and timestamp per conversation.

Setup, design rationale, and deploy steps: **[GUIDE.md](./GUIDE.md)**

## Sepolia deployment (kfc)

| Item | Location |
|------|----------|
| Contract | `0x69d3D7D9E50141faef9AC957D6450a4ccb37c404` |
| ABI | `fidelity-ui/MessageFidelity.abi.json` |
| Network metadata | `fidelity-ui/deployment.json` |

**Deploy:** The Sepolia address above is an old demo contract (open `storeHash`, overwrites allowed). Current Solidity is owner-only and write-once per `recordId`. Redeploy with `npm run deploy:sepolia`, update `MESSAGE_FIDELITY_ADDRESS` and `deployment.json`, anchor with the deployer key. New `segmentKey` per batch when the tree grows ([GUIDE.md](./GUIDE.md)).

## Commands

```bash
npm install
npm run build      # compile TS → dist/
npm run compile    # compile Solidity
npm test
npm run deploy:sepolia
npm run e2e        # crypto backend + Sepolia anchor
npm run serve:fidelity
```

## Quick API

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
