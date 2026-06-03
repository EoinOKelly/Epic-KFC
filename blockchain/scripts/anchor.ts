import { ethers } from "hardhat";
import { hashMessageLeaf } from "../src/merkle";
import {
  buildConversationMerkleTree,
  deriveConversationSegmentRecordId,
} from "../src/conversation";

async function main() {
  const args = process.argv.slice(2);
  const getArg = (flag: string) => {
    const i = args.indexOf(flag);
    return i >= 0 ? args[i + 1] : undefined;
  };

  const contractAddress = getArg("--contract") ?? process.env.MESSAGE_FIDELITY_ADDRESS;
  const userA = getArg("--userA");
  const userB = getArg("--userB");
  const messageId = getArg("--messageId");
  const message = getArg("--message");

  if (!contractAddress || !userA || !userB || !messageId || message === undefined) {
    throw new Error(
      "Usage: --contract <addr> --userA <uuid> --userB <uuid> --messageId <uuid> --message <text>"
    );
  }

  const messages = [
    { messageId, plaintext: message, createdAt: new Date().toISOString() },
  ];
  const tree = buildConversationMerkleTree(messages);
  const recordId = deriveConversationSegmentRecordId(
    userA,
    userB,
    String(messages.length)
  );

  const fidelity = await ethers.getContractAt("MessageFidelity", contractAddress);
  const tx = await fidelity.storeHash(recordId, tree.root);
  console.log("Tx:", tx.hash);
  await tx.wait();
  console.log("Anchored Merkle root", {
    recordId,
    merkleRoot: tree.root,
    leaf: hashMessageLeaf(messageId, message),
  });
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
