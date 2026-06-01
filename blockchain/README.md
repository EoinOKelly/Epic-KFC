# Blockchain — Merkle message integrity

See **[GUIDE.md](./GUIDE.md)** for setup steps and file explanations.

## Quick commands

```bash
npm install
npm run build      # compile TS API → dist/
npm run compile    # compile Solidity
npm test
npm run deploy:sepolia
npm run e2e        # crypto backend + Sepolia anchor
npm run serve:fidelity
```

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
