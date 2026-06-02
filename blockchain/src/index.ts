import { anchorClientFromEnv, createAnchorClient, MessageFidelityClient } from "./anchorClient";
import {
  buildConversationMerkleTree,
  deriveConversationRecordId,
  type AnchoredMessage,
} from "./conversation";
import { hashMessageLeaf, verifyMerkleProof, type Hex32 } from "./merkle";

export {
  hashMessageLeaf,
  hashPair,
  buildMerkleTree,
  verifyMerkleProof,
  type Hex32,
} from "./merkle";

export {
  deriveConversationRecordId,
  buildConversationMerkleTree,
  type AnchoredMessage,
} from "./conversation";

export {
  MessageFidelityClient,
  createAnchorClient,
  anchorClientFromEnv,
  readOnlyClientFromEnv,
  MESSAGE_FIDELITY_ABI,
  type AnchorClientConfig,
  type AnchorMerkleRootResult,
  type VerifyOnChainResult,
} from "./anchorClient";

export interface AnchorConversationResult {
  recordId: Hex32;
  merkleRoot: Hex32;
  messageCount: number;
  chain: import("./anchorClient").AnchorMerkleRootResult;
}

export async function anchorConversationOnChain(
  userIdA: string,
  userIdB: string,
  messages: AnchoredMessage[],
  client?: MessageFidelityClient
): Promise<AnchorConversationResult> {
  const anchorClient = client ?? anchorClientFromEnv();
  const { root } = buildConversationMerkleTree(messages);
  const recordId = deriveConversationRecordId(userIdA, userIdB);
  const chain = await anchorClient.anchorMerkleRoot(recordId, root);

  return {
    recordId,
    merkleRoot: root,
    messageCount: messages.length,
    chain,
  };
}

export interface VerifyMessageResult {
  pass: boolean;
  leaf: Hex32;
  onChainRoot: Hex32;
  anchoredAt: number;
  merkleProof: Hex32[];
}

export async function verifyMessageOnChain(
  userIdA: string,
  userIdB: string,
  allMessagesInConversation: AnchoredMessage[],
  messageIdToVerify: string,
  client?: MessageFidelityClient
): Promise<VerifyMessageResult> {
  const anchorClient = client ?? anchorClientFromEnv();
  const recordId = deriveConversationRecordId(userIdA, userIdB);
  const tree = buildConversationMerkleTree(allMessagesInConversation);
  const target = allMessagesInConversation.find((m) => m.messageId === messageIdToVerify);
  if (!target) {
    throw new Error(`Message ${messageIdToVerify} not in conversation list`);
  }

  const leaf = hashMessageLeaf(target.messageId, target.plaintext);
  const merkleProof = tree.getProofForMessage(messageIdToVerify);
  const offChainOk = tree.verifyMessage(messageIdToVerify, target.plaintext, merkleProof);
  const onChain = await anchorClient.verifyMessageInHistory(recordId, leaf, merkleProof);

  return {
    pass: offChainOk && onChain.pass,
    leaf,
    onChainRoot: onChain.onChainRoot,
    anchoredAt: onChain.anchoredAt,
    merkleProof,
  };
}
