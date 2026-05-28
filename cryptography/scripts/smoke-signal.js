/**
 * Fast regression check (no verbose logs). For step-by-step output: npm run demo:signal
 */
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
} = require("../dist/signal");

const verbose = process.argv.includes("--verbose") || process.env.VERBOSE === "1";
const log = (...args) => verbose && console.log("[smoke]", ...args);

async function main() {
  log("generating alice + bob devices…");
  const alice = await generateDevice("alice", 1);
  const bob = await generateDevice("bob", 1);

  const tofu = new Map();
  const bobBundle = deviceToPublicBundle(bob);
  const tofuResult = verifyIdentityTofu(tofu, "bob", 1, identityKeyBytes(bobBundle));
  if (tofuResult.status === "first_use") pinIdentity(tofu, tofuResult.record);
  log("TOFU:", tofuResult.status);

  log("establishSession alice → bob…");
  await establishSession(alice, bobBundle, "bob", 1);

  log("encrypt alice → bob…");
  const wire1 = await encryptForRecipient(alice, "bob", 1, "hello bob");
  log("wire1 type:", wire1.type, "bodyB64 chars:", wire1.bodyB64.length);

  const plain1 = await decryptFromSender(bob, "alice", 1, wire1);
  console.log("bob received:", plain1.toString("utf8"));

  log("encrypt bob → alice…");
  const wire2 = await encryptForRecipient(bob, "alice", 1, "hello alice");
  log("wire2 type:", wire2.type);

  const plain2 = await decryptFromSender(alice, "bob", 1, wire2);
  console.log("alice received:", plain2.toString("utf8"));

  const { deviceKeys } = await deviceToDbRows(bob);
  const fromDb = preKeyBundleFromDb({
    ...deviceKeys,
    one_time_prekey_id: 1,
    one_time_prekey_public_b64: null,
  });
  if (!fromDb.identityKey) throw new Error("bundle from DB missing identity key");

  console.log("smoke OK");
  if (!verbose) console.log("(run npm run demo:signal for a full walkthrough)");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
