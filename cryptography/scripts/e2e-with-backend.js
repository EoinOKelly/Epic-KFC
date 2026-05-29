const {
  generateDevice,
  establishSession,
  encryptForRecipient,
  decryptFromSender,
  deviceToDbRows,
  deviceKeyUploadPayloadFromRow,
  preKeyBundleFromApiResponse,
  verifyIdentityTofu,
  pinIdentity,
  identityKeyBytes,
} = require("../dist/signal");
const { serializeWireMessage, deserializeWireMessage } = require("../dist/wireFormat");

const BASE = process.env.API_BASE_URL || "http://127.0.0.1:8000";
const PASSWORD = process.env.E2E_PASSWORD || "correct-horse-battery-staple";
const SUFFIX = process.env.E2E_SUFFIX || String(Date.now()).slice(-6);

const ALICE = { username: `e2e-alice-${SUFFIX}`, email: `alice-${SUFFIX}@example.com` };
const BOB = { username: `e2e-bob-${SUFFIX}`, email: `bob-${SUFFIX}@example.com` };
const DEVICE_ID = 1;

function log(step, message) {
  console.log(`\n[${step}] ${message}`);
}

async function api(path, options = {}) {
  const url = `${BASE}/api/v1${path}`;
  const { headers: optionHeaders, ...rest } = options;
  const res = await fetch(url, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(optionHeaders || {}),
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
    log("auth", `registered ${user.username}`);
  } catch (err) {
    if (!String(err.message).includes("409")) throw err;
    log("auth", `${user.username} already exists — logging in`);
  }

  const tokens = await api("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username_or_email: user.username, password: PASSWORD }),
  });
  return tokens.access_token;
}

async function uploadDevice(token, userId, device) {
  const { deviceKeys, oneTimePreKeys } = await deviceToDbRows(device);
  const body = deviceKeyUploadPayloadFromRow(deviceKeys);

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

  log("keys", `uploaded device ${DEVICE_ID} for user ${userId.slice(0, 8)}…`);
}

async function main() {
  console.log("=".repeat(60));
  console.log("E2E: cryptography/ → FastAPI backend");
  console.log("=".repeat(60));
  console.log(`API: ${BASE}`);

  log("1", "Register + login Alice and Bob");
  const aliceToken = await registerOrLogin(ALICE);
  const bobToken = await registerOrLogin(BOB);

  const aliceMe = await api("/auth/me", { headers: { Authorization: `Bearer ${aliceToken}` } });
  const bobMe = await api("/auth/me", { headers: { Authorization: `Bearer ${bobToken}` } });
  const aliceUserId = aliceMe.id;
  const bobUserId = bobMe.id;

  log("2", "Generate local Signal devices (private keys stay in Node — not sent to server)");
  const aliceDevice = await generateDevice(aliceUserId, DEVICE_ID);
  const bobDevice = await generateDevice(bobUserId, DEVICE_ID);

  log("3", "Upload public keys only to backend");
  await uploadDevice(aliceToken, aliceUserId, aliceDevice);
  await uploadDevice(bobToken, bobUserId, bobDevice);

  log("4", "Alice fetches Bob's pre-key bundle (server relay)");
  const bobBundleApi = await api(
    `/keys/users/${bobUserId}/devices/${DEVICE_ID}/prekey-bundle`,
    { headers: { Authorization: `Bearer ${aliceToken}` } }
  );
  const bobBundle = preKeyBundleFromApiResponse(bobBundleApi);

  const tofu = new Map();
  const tofuResult = verifyIdentityTofu(tofu, bobUserId, DEVICE_ID, identityKeyBytes(bobBundle));
  if (tofuResult.status === "first_use") pinIdentity(tofu, tofuResult.record);
  log("tofu", `Bob identity: ${tofuResult.status}`);

  log("5", "Alice establishes session + encrypts (cryptography/ — not on server)");
  await establishSession(aliceDevice, bobBundle, bobUserId, DEVICE_ID);
  const plaintext = "hello bob via backend relay";
  const wire = await encryptForRecipient(aliceDevice, bobUserId, DEVICE_ID, plaintext);
  const wireJson = serializeWireMessage(wire);
  log("encrypt", `wire type=${wire.type}, bodyB64 chars=${wire.bodyB64.length}`);

  log("6", "POST opaque wire_payload_json to backend");
  const sent = await api("/messages", {
    method: "POST",
    headers: { Authorization: `Bearer ${aliceToken}` },
    body: JSON.stringify({
      sender_device_id: DEVICE_ID,
      recipient_user_id: bobUserId,
      recipient_device_id: DEVICE_ID,
      wire_payload_json: wireJson,
      consumed_one_time_prekey_id: bobBundleApi.oneTimePreKeyId ?? undefined,
    }),
  });
  log("relay", `message id=${sent.id} stored (server never decrypts)`);

  log("7", "Bob fetches inbox + decrypts locally");
  const inbox = await api("/messages/received?limit=10", {
    headers: { Authorization: `Bearer ${bobToken}` },
  });
  const row = inbox.find((m) => m.id === sent.id);
  if (!row) throw new Error("Bob did not receive message in inbox");

  const wireFromServer = deserializeWireMessage(row.wire_payload_json);
  const decrypted = await decryptFromSender(bobDevice, aliceUserId, DEVICE_ID, wireFromServer);
  log("decrypt", `Bob read: "${decrypted.toString("utf8")}"`);

  if (decrypted.toString("utf8") !== plaintext) {
    throw new Error("plaintext mismatch after backend round-trip");
  }

  log("8", "Bob replies through backend");
  const replyText = "hello alice — reply through server";
  const replyWire = await encryptForRecipient(bobDevice, aliceUserId, DEVICE_ID, replyText);
  await api("/messages", {
    method: "POST",
    headers: { Authorization: `Bearer ${bobToken}` },
    body: JSON.stringify({
      sender_device_id: DEVICE_ID,
      recipient_user_id: aliceUserId,
      recipient_device_id: DEVICE_ID,
      wire_payload_json: serializeWireMessage(replyWire),
    }),
  });

  const aliceInbox = await api("/messages/received?limit=10", {
    headers: { Authorization: `Bearer ${aliceToken}` },
  });
  const replyRow = aliceInbox[0];
  const replyDecrypted = await decryptFromSender(
    aliceDevice,
    bobUserId,
    DEVICE_ID,
    deserializeWireMessage(replyRow.wire_payload_json)
  );
  log("decrypt", `Alice read: "${replyDecrypted.toString("utf8")}"`);

  console.log("\n" + "=".repeat(60));
  console.log("E2E OK — crypto + backend relay working together");
  console.log("=".repeat(60) + "\n");
}

main().catch((err) => {
  console.error("\nE2E FAILED:", err.message);
  console.error("\nIs the API running?  uvicorn app.main:app --reload");
  console.error("Is Postgres migrated?  alembic upgrade head\n");
  process.exit(1);
});
