import { ethers } from "ethers";
import { buildMerkleTree, hashMessageLeaf, type Hex32 } from "./merkle";

export interface AnchoredMessage {
  messageId: string;
  plaintext: string;
  createdAt?: string;
}

export function deriveConversationRecordId(
  userIdA: string,
  userIdB: string
): Hex32 {
  const sorted = [userIdA, userIdB].sort();
  return ethers.id(`direct:${sorted[0]}:${sorted[1]}`) as Hex32;
}

export function deriveConversationSegmentRecordId(
  userIdA: string,
  userIdB: string,
  segmentKey: string
): Hex32 {
  const sorted = [userIdA, userIdB].sort();
  return ethers.id(
    `direct:${sorted[0]}:${sorted[1]}:segment:${segmentKey}`
  ) as Hex32;
}

export function buildConversationMerkleTree(messages: AnchoredMessage[]) {
  if (messages.length === 0) {
    throw new Error("Conversation must contain at least one message");
  }

  const ordered = [...messages].sort((a, b) => {
    if (a.createdAt && b.createdAt && a.createdAt !== b.createdAt) {
      return a.createdAt.localeCompare(b.createdAt);
    }
    return a.messageId.localeCompare(b.messageId);
  });

  const leaves = ordered.map((m) => hashMessageLeaf(m.messageId, m.plaintext));
  const tree = buildMerkleTree(leaves);

  return {
    orderedMessages: ordered,
    leaves,
    root: tree.root,
    getProofForMessage: (messageId: string): Hex32[] => {
      const index = ordered.findIndex((m) => m.messageId === messageId);
      if (index < 0) {
        throw new Error(`Message not in conversation tree: ${messageId}`);
      }
      return tree.getProof(index);
    },
    verifyMessage: (messageId: string, plaintext: string, proof: Hex32[]): boolean => {
      const leaf = hashMessageLeaf(messageId, plaintext);
      return tree.verifyProof(leaf, proof);
    },
  };
}
