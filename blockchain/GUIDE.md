# Blockchain setup

## What “fidelity” means here

**Not** Fidelity Investments. It means **message fidelity** — does the text still match the hash we stored on-chain? Pass = unchanged, Fail = tampered or wrong data.

The folder `fidelity-ui/` is just a small web page to run that check.

---

## Deploy with your Sepolia wallet (0.05 ETH is plenty)

### 1. Get an RPC URL

Sign up at [Alchemy](https://www.alchemy.com/) or [Infura](https://infura.io/), create an app on **Sepolia**, copy the HTTPS URL.

### 2. Export your wallet private key

In MetaMask (or whatever you used):

- Account → three dots → **Account details** → **Show private key**
- Copy it — starts with `0x`

Never commit this. Never use mainnet keys.

### 3. Create `blockchain/.env`

```env
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
DEPLOYER_PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE
```

### 4. Deploy

```powershell
cd "c:\Users\eoino\Year2\Epic Messaging\blockchain"
npm install
npm run compile
npm run deploy:sepolia
```

You should see something like:

```
MessageFidelity deployed to: 0xABC...
```

### 5. Add contract address to `.env`

```env
MESSAGE_FIDELITY_ADDRESS=0xABC...
```

### 6. Check on Etherscan

Open `https://sepolia.etherscan.io/address/YOUR_CONTRACT` — you should see the deploy transaction.

---

## Run the full demo

Terminal 1 — backend (if not already running):

```powershell
cd server\backend
uvicorn app.main:app --reload
```

Terminal 2 — crypto build + blockchain e2e:

```powershell
cd cryptography
npm run build

cd ..\blockchain
npm run build
npm run e2e
```

That sends encrypted messages through the API, builds the Merkle tree, anchors the root on Sepolia, and verifies one message.

Skip Sepolia (Merkle math only):

```powershell
$env:SKIP_BLOCKCHAIN="1"; npm run e2e
```

---

## Verify in the browser

```powershell
npm run serve:fidelity
```

Open http://localhost:5173 → **Load deployment.json** → fill RPC URL, user UUIDs, messages JSON → **Verify**.

---

## Files (short)

| File | Role |
|------|------|
| `contracts/MessageFidelity.sol` | On-chain Merkle root storage |
| `src/merkle.ts` | Tree + proofs |
| `src/index.ts` | `anchorConversationOnChain`, `verifyMessageOnChain` |
| `scripts/deploy.ts` | Deploy to Sepolia |
| `scripts/e2e-with-backend.js` | End-to-end demo |
| `fidelity-ui/` | Pass/Fail checker page |
