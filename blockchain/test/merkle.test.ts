import { expect } from "chai";
import {
  buildMerkleTree,
  hashMessageLeaf,
  verifyMerkleProof,
} from "../src/merkle";
import { buildConversationMerkleTree } from "../src/conversation";

describe("Merkle tree (off-chain)", () => {
  it("builds root and verifies each leaf with proof", () => {
    const leaves = [
      hashMessageLeaf("msg-1", "hello"),
      hashMessageLeaf("msg-2", "world"),
      hashMessageLeaf("msg-3", "integrity"),
    ];
    const tree = buildMerkleTree(leaves);

    leaves.forEach((leaf, index) => {
      const proof = tree.getProof(index);
      expect(tree.verifyProof(leaf, proof)).to.equal(true);
      expect(verifyMerkleProof(tree.root, leaf, proof)).to.equal(true);
    });
  });

  it("fails when plaintext is tampered", () => {
    const messages = [
      { messageId: "a", plaintext: "one" },
      { messageId: "b", plaintext: "two" },
    ];
    const tree = buildConversationMerkleTree(messages);
    const proof = tree.getProofForMessage("a");
    expect(tree.verifyMessage("a", "one", proof)).to.equal(true);
    expect(tree.verifyMessage("a", "TAMPERED", proof)).to.equal(false);
  });
});
