/**
 * Interactive-style demo: shows what smoke:signal does, step by step.
 *
 * Run:  npm run demo:signal
 *       npm run demo:signal -- --save-wire   (writes wire JSON files to /tmp)
 */

const fs = require("node:fs");
const path = require("node:path");
const {
  generateDevice,
  establishSession,
  encryptForRecipient,
  decryptFromSender,
  deviceToPublicBundle,
  preKeyBundleFromDb,
  deviceToDbRows,
  verifyIdentityTofu,
  pinIdentity,
  identityKeyBytes,
  SIGNAL_PROTOCOL,
} = require("../dist/signal");
const { serializeWireMessage, deserializeWireMessage } = require("../dist/wireFormat");

const saveWire = process.argv.includes("--save-wire");
const outDir = path.join(__dirname, "..", "demo-output");

function section(title) {
  console.log("\n" + "=".repeat(60));
  console.log(title);
  console.log("=".repeat(60));
}

function step(n, text) {
  console.log(`\n[${n}] ${text}`);
}

function kv(key, value) {
  const display =
    typeof value === "string" && value.length > 72
      ? value.slice(0, 36) + "…" + value.slice(-12) + ` (${value.length} chars)`
      : value;
  console.log(`    ${key}: ${display}`);
}

function previewJson(label, obj) {
  const json = JSON.stringify(obj, null, 2);
  const lines = json.split("\n");
  console.log(`    ${label} (first lines):`);
  for (const line of lines.slice(0, 12)) console.log(`      ${line}`);
  if (lines.length > 12) console.log(`      … (${lines.length - 12} more lines)`);
}

async function main() {
  section("Epic Messaging — Signal E2EE demo (local only, no server)");
  console.log("This script runs entirely on your machine. Nothing is sent over the network.");
  kv("Protocol stack", SIGNAL_PROTOCOL.implementation);
  kv("Session setup", SIGNAL_PROTOCOL.keyAgreement);
  kv("Ratchet", SIGNAL_PROTOCOL.ratchet);
  kv("Your message bytes (brief)", SIGNAL_PROTOCOL.applicationPayload);
  kv("Library transport (inner)", SIGNAL_PROTOCOL.transportPayload);

  // --- Alice & Bob devices ---
  section("1) Generate devices (identity + pre-keys)");
  step(1, "Alice: generateDevice('alice', 1)");
  const alice = await generateDevice("alice", 1);
  kv("registrationId", alice.registrationId);
  kv("signedPreKeyId", alice.signedPreKeyId);
  kv("oneTimePreKeyId", alice.oneTimePreKeyId);
  console.log("    → Creates Curve25519 identity key, signed pre-key, one OPK, in-memory store.");

  step(2, "Bob: generateDevice('bob', 1)");
  const bob = await generateDevice("bob", 1);
  kv("registrationId", bob.registrationId);

  // --- TOFU ---
  section("2) TOFU — trust on first use (client-only)");
  const tofu = new Map();
  const bobBundle = deviceToPublicBundle(bob);
  const bobIdentityB64 = Buffer.from(bobBundle.identityKey).toString("base64");
  kv("Bob identity key (public, base64 preview)", bobIdentityB64);

  step(3, "Alice checks Bob's identity before messaging");
  const tofuResult = verifyIdentityTofu(tofu, "bob", 1, identityKeyBytes(bobBundle));
  kv("TOFU result", tofuResult.status);
  if (tofuResult.status === "first_use") {
    pinIdentity(tofu, tofuResult.record);
    console.log("    → First time seeing Bob: pinned identity locally (server does not do this).");
  }

  // --- Session ---
  section("3) Session setup — X3DH (Alice → Bob)");
  step(4, "establishSession(alice, bobBundle, 'bob', 1)");
  console.log("    → Alice runs X3DH using Bob's public bundle (as if fetched from your API).");
  console.log("    → Session state saved in alice.store only.");
  await establishSession(alice, bobBundle, "bob", 1);
  console.log("    ✓ Session ready on Alice's side.");

  // --- Encrypt message 1 ---
  section("4) Alice encrypts → Bob decrypts (first message)");
  const plaintext1 = "hello bob";
  step(5, `encryptForRecipient(alice → bob, "${plaintext1}")`);
  console.log("    Inside encryptForRecipient:");
  console.log("      a) Plaintext → AES-256-GCM envelope (random key + AAD) — brief compliance");
  console.log("      b) Envelope JSON → libsignal SessionCipher.encrypt → PreKeyWhisperMessage (type 3)");
  const wire1 = await encryptForRecipient(alice, "bob", 1, plaintext1);
  kv("wire.format", wire1.format);
  kv("wire.type", wire1.type + " (3 = first message / establishes Bob's session on decrypt)");
  kv("wire.bodyB64 length", wire1.bodyB64.length + " chars (opaque Signal protobuf, base64)");
  if (wire1.registrationId != null) kv("wire.registrationId", wire1.registrationId);

  const wireJson1 = serializeWireMessage(wire1);
  previewJson("wire_payload_json (what backend would store)", JSON.parse(wireJson1));

  if (saveWire) {
    fs.mkdirSync(outDir, { recursive: true });
    const p = path.join(outDir, "alice-to-bob-wire.json");
    fs.writeFileSync(p, wireJson1, "utf8");
    kv("saved", p);
  }

  step(6, "decryptFromSender(bob, from alice, wire1)");
  console.log("    → Bob decrypts Signal layer, then unwraps GCM envelope → plaintext.");
  const plain1 = await decryptFromSender(bob, "alice", 1, wire1);
  kv("Bob decrypted plaintext", plain1.toString("utf8"));
  if (plain1.toString("utf8") !== plaintext1) throw new Error("decrypt mismatch");

  // --- Reply ---
  section("5) Bob replies → Alice decrypts (ratchet message)");
  const plaintext2 = "hello alice";
  step(7, `encryptForRecipient(bob → alice, "${plaintext2}")`);
  const wire2 = await encryptForRecipient(bob, "alice", 1, plaintext2);
  kv("wire.type", wire2.type + " (1 = WhisperMessage on established session)");
  const plain2 = await decryptFromSender(alice, "bob", 1, wire2);
  kv("Alice decrypted plaintext", plain2.toString("utf8"));

  // --- Round-trip wire serialize ---
  section("6) Wire format round-trip");
  step(8, "serializeWireMessage → deserializeWireMessage");
  const roundTrip = deserializeWireMessage(serializeWireMessage(wire1));
  if (roundTrip.bodyB64 !== wire1.bodyB64) throw new Error("wire round-trip failed");
  console.log("    ✓ JSON wire blob survives serialize/deserialize unchanged.");

  // --- DB mapping smoke ---
  section("7) DB row mapping (what you'd upload to FastAPI)");
  step(9, "deviceToDbRows(bob) + preKeyBundleFromDb");
  const { deviceKeys, oneTimePreKeys } = await deviceToDbRows(bob);
  kv("device_keys.identity_key_public_b64 (preview)", deviceKeys.identity_key_public_b64.slice(0, 40) + "…");
  kv("one_time_prekeys count", oneTimePreKeys.length);
  const fromDb = preKeyBundleFromDb({
    ...deviceKeys,
    one_time_prekey_id: oneTimePreKeys[0]?.prekey_id ?? null,
    one_time_prekey_public_b64: oneTimePreKeys[0]?.prekey_public_b64 ?? null,
  });
  console.log("    ✓ Can rebuild libsignal bundle from DB-shaped rows.");

  section("DONE — all local checks passed");
  console.log("\nNext: connect to backend with Step 2 (wire validator) + e2e script.");
  console.log("Quick check only:  npm run smoke:signal");
  console.log("This verbose demo: npm run demo:signal");
  console.log("Save wire files:   npm run demo:signal -- --save-wire\n");
}

main().catch((e) => {
  console.error("\nDEMO FAILED:", e);
  process.exit(1);
});
