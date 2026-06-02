require("dotenv").config();

const crypto = require("../../cryptography/dist/signal");
const wire = require("../../cryptography/dist/wireFormat");
const {
  buildConversationMerkleTree,
  deriveConversationRecordId,
  anchorConversationOnChain,
  verifyMessageOnChain,
  createAnchorClient,
} = require("../dist/index");

const BASE = process.env.API_BASE_URL || "http://127.0.0.1:8000";
const PASSWORD = process.env.E2E_PASSWORD || "correct-horse-battery-staple";
const SUFFIX = process.env.E2E_SUFFIX || String(Date.now()).slice(-6);
const SKIP_CHAIN = process.env.SKIP_BLOCKCHAIN === "1";

const ALICE = { username: `merkle-alice-${SUFFIX}`, email: `malice-${SUFFIX}@example.com` };
const BOB = { username: `merkle-bob-${SUFFIX}`, email: `mbob-${SUFFIX}@example.com` };
const DEVICE_ID = 1;

function log(step, msg) {
  console.log(`\n[${step}] ${msg}`);
}

async function api(path, options = {}) {
  const url = `${BASE}/api/v1${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let body;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    throw new Error(`${options.method || "GET"} ${path} → ${res.status}: ${JSON.stringify(body)}`);
  }
  return body;
}

async function registerOrLogin(user) {
  try {
    await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username: user.username, email: user.email, password: PASSWORD }),
    });
  } catch (err) {
    if (!String(err.message).includes("409")) throw err;
  }
  const tokens = await api("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username_or_email: user.username, password: PASSWORD }),
  });
  return tokens.access_token;
}

async function uploadDevice(token, userId, device) {
  const { deviceKeys, oneTimePreKeys } = await crypto.deviceToDbRows(device);
  const body = crypto.deviceKeyUploadPayloadFromRow(deviceKeys);
  await api(`/keys/devices/${DEVICE_ID}`, {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (oneTimePreKeys.length > 0) {
    await api(`/keys/devices/${DEVICE_ID}/one-time-prekeys`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        prekeys: oneTimePreKeys.map((opk) => ({
          device_id: opk.device_id,
          prekey_id: opk.prekey_id,
          prekey_public_b64: opk.prekey_public_b64,
        })),
      }),
    });
  }
  log("keys", `uploaded device for ${userId.slice(0, 8)}…`);
}

async function main() {
  console.log("=".repeat(60));
  console.log("E2E: crypto relay + Merkle anchor");
  console.log("=".repeat(60));

  log("1", "Auth + devices");
  const aliceToken = await registerOrLogin(ALICE);
  const bobToken = await registerOrLogin(BOB);
  const aliceMe = await api("/auth/me", { headers: { Authorization: `Bearer ${aliceToken}` } });
  const bobMe = await api("/auth/me", { headers: { Authorization: `Bearer ${bobToken}` } });
  const aliceUserId = aliceMe.id;
  const bobUserId = bobMe.id;

  const aliceDevice = await crypto.generateDevice(aliceUserId, DEVICE_ID);
  const bobDevice = await crypto.generateDevice(bobUserId, DEVICE_ID);
  await uploadDevice(aliceToken, aliceUserId, aliceDevice);
  await uploadDevice(bobToken, bobUserId, bobDevice);

  const bobBundleApi = await api(
    `/keys/users/${bobUserId}/devices/${DEVICE_ID}/prekey-bundle`,
    { headers: { Authorization: `Bearer ${aliceToken}` } }
  );
  const bobBundle = crypto.preKeyBundleFromApiResponse(bobBundleApi);
  const tofu = new Map();
  const tofuResult = crypto.verifyIdentityTofu(tofu, bobUserId, DEVICE_ID, crypto.identityKeyBytes(bobBundle));
  if (tofuResult.status === "first_use") crypto.pinIdentity(tofu, tofuResult.record);

  log("2", "Alice → Bob message");
  await crypto.establishSession(aliceDevice, bobBundle, bobUserId, DEVICE_ID);
  const plaintext1 = "hello bob — merkle anchor test";
  const wire1 = await crypto.encryptForRecipient(aliceDevice, bobUserId, DEVICE_ID, plaintext1);
  const sent1 = await api("/messages", {
    method: "POST",
    headers: { Authorization: `Bearer ${aliceToken}` },
    body: JSON.stringify({
      sender_device_id: DEVICE_ID,
      recipient_user_id: bobUserId,
      recipient_device_id: DEVICE_ID,
      wire_payload_json: wire.serializeWireMessage(wire1),
      consumed_one_time_prekey_id: bobBundleApi.oneTimePreKeyId ?? undefined,
    }),
  });

  log("3", "Bob reply");
  const replyText = "hello alice — reply for merkle tree";
  const replyWire = await crypto.encryptForRecipient(bobDevice, aliceUserId, DEVICE_ID, replyText);
  const sent2 = await api("/messages", {
    method: "POST",
    headers: { Authorization: `Bearer ${bobToken}` },
    body: JSON.stringify({
      sender_device_id: DEVICE_ID,
      recipient_user_id: aliceUserId,
      recipient_device_id: DEVICE_ID,
      wire_payload_json: wire.serializeWireMessage(replyWire),
    }),
  });

  const conversationMessages = [
    { messageId: sent1.id, plaintext: plaintext1, createdAt: sent1.created_at },
    { messageId: sent2.id, plaintext: replyText, createdAt: sent2.created_at },
  ];

  log("4", "Build Merkle tree (off-chain)");
  const tree = buildConversationMerkleTree(conversationMessages);
  console.log("  recordId:", deriveConversationRecordId(aliceUserId, bobUserId));
  console.log("  merkleRoot:", tree.root);
  console.log("  leaves:", tree.leaves.length);

  const proof = tree.getProofForMessage(sent1.id);
  if (!tree.verifyMessage(sent1.id, plaintext1, proof)) {
    throw new Error("Local Merkle proof failed");
  }
  log("merkle", "local proof OK for first message");

  if (SKIP_CHAIN) {
    console.log("\nSKIP_BLOCKCHAIN=1 — skipping Sepolia tx");
    return;
  }

  log("5", "Anchor Merkle root on Sepolia");
  const client = createAnchorClient({
    rpcUrl: process.env.SEPOLIA_RPC_URL,
    privateKey: process.env.DEPLOYER_PRIVATE_KEY,
    contractAddress: process.env.MESSAGE_FIDELITY_ADDRESS,
  });
  const anchor = await anchorConversationOnChain(
    aliceUserId,
    bobUserId,
    conversationMessages,
    client
  );
  console.log("  tx:", anchor.chain.transactionHash);

  log("6", "Verify message on-chain via Merkle proof");
  const verify = await verifyMessageOnChain(
    aliceUserId,
    bobUserId,
    conversationMessages,
    sent1.id,
    client
  );
  if (!verify.pass) throw new Error("On-chain Merkle verification failed");
  log("verify", "Pass — message proven in anchored history");

  console.log("\n" + "=".repeat(60));
  console.log("E2E OK — Merkle root anchored + proof verified");
  console.log("=".repeat(60));
}

main().catch((err) => {
  console.error("\nE2E FAILED:", err.message);
  process.exit(1);
});
