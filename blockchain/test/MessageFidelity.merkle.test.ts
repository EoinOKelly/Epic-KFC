import { expect } from "chai";
import { ethers } from "hardhat";
import { MessageFidelity } from "../typechain-types";
import {
  buildConversationMerkleTree,
  deriveConversationRecordId,
} from "../src/conversation";
import { hashMessageLeaf } from "../src/merkle";

describe("MessageFidelity Merkle integration", () => {
  let fidelity: MessageFidelity;

  const alice = "11111111-1111-1111-1111-111111111111";
  const bob = "22222222-2222-2222-2222-222222222222";
  const recordId = deriveConversationRecordId(alice, bob);

  const messages = [
    { messageId: "m1", plaintext: "hello bob", createdAt: "2026-01-01T00:00:00.000Z" },
    { messageId: "m2", plaintext: "hello alice", createdAt: "2026-01-01T00:01:00.000Z" },
  ];

  beforeEach(async () => {
    fidelity = await ethers.deployContract("MessageFidelity");
  });

  it("anchors Merkle root and verifies message inclusion on-chain", async () => {
    const tree = buildConversationMerkleTree(messages);
    await fidelity.storeHash(recordId, tree.root);

    const leaf = hashMessageLeaf("m1", "hello bob");
    const proof = tree.getProofForMessage("m1");

    expect(await fidelity.verifyMerkleProof(leaf, tree.root, proof)).to.equal(true);
    expect(await fidelity.verifyMessageInHistory(recordId, leaf, proof)).to.equal(
      true
    );

    const badLeaf = hashMessageLeaf("m1", "tampered");
    expect(await fidelity.verifyMessageInHistory(recordId, badLeaf, proof)).to.equal(
      false
    );
  });

  it("updates root when conversation grows", async () => {
    const first = buildConversationMerkleTree([messages[0]]);
    await fidelity.storeHash(recordId, first.root);

    const full = buildConversationMerkleTree(messages);
    await fidelity.storeHash(recordId, full.root);

    const [storedRoot] = await fidelity.getHash(recordId);
    expect(storedRoot).to.equal(full.root);
    expect(storedRoot).to.not.equal(first.root);
  });
});
