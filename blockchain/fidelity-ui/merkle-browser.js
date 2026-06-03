function hashMessageLeaf(messageId, plaintext) {
  const payloadHash = ethers.keccak256(ethers.toUtf8Bytes(plaintext));
  return ethers.keccak256(
    ethers.solidityPacked(["string", "bytes32"], [messageId, payloadHash])
  );
}

function hashPair(a, b) {
  const left = a.toLowerCase();
  const right = b.toLowerCase();
  const [first, second] = left <= right ? [left, right] : [right, left];
  return ethers.keccak256(
    ethers.solidityPacked(["bytes32", "bytes32"], [first, second])
  );
}

function buildMerkleTree(leaves) {
  if (!leaves.length) throw new Error("Need at least one leaf");
  const layers = [leaves.map((l) => l.toLowerCase())];
  while (layers[layers.length - 1].length > 1) {
    const current = layers[layers.length - 1];
    const next = [];
    for (let i = 0; i < current.length; i += 2) {
      next.push(
        i + 1 < current.length
          ? hashPair(current[i], current[i + 1])
          : hashPair(current[i], current[i])
      );
    }
    layers.push(next);
  }
  const root = layers[layers.length - 1][0];

  function getProof(leafIndex) {
    const proof = [];
    let index = leafIndex;
    for (let layer = 0; layer < layers.length - 1; layer++) {
      const layerNodes = layers[layer];
      const siblingIndex = index % 2 === 0 ? index + 1 : index - 1;
      proof.push(
        siblingIndex < layerNodes.length ? layerNodes[siblingIndex] : layerNodes[index]
      );
      index = Math.floor(index / 2);
    }
    return proof;
  }

  return { root, getProof };
}

function deriveConversationRecordId(userIdA, userIdB) {
  const sorted = [userIdA, userIdB].sort();
  return ethers.id(`direct:${sorted[0]}:${sorted[1]}`);
}

function deriveConversationSegmentRecordId(userIdA, userIdB, segmentKey) {
  const sorted = [userIdA, userIdB].sort();
  return ethers.id(`direct:${sorted[0]}:${sorted[1]}:segment:${segmentKey}`);
}

function buildConversationMerkleTree(messages) {
  const ordered = [...messages].sort((a, b) => {
    if (a.createdAt && b.createdAt && a.createdAt !== b.createdAt) {
      return a.createdAt.localeCompare(b.createdAt);
    }
    return a.messageId.localeCompare(b.messageId);
  });
  const leaves = ordered.map((m) => hashMessageLeaf(m.messageId, m.plaintext));
  const tree = buildMerkleTree(leaves);
  return {
    ordered,
    root: tree.root,
    getProofForMessage(messageId) {
      const index = ordered.findIndex((m) => m.messageId === messageId);
      if (index < 0) throw new Error("Message not in tree");
      return tree.getProof(index);
    },
    leafFor(messageId, plaintext) {
      return hashMessageLeaf(messageId, plaintext);
    },
  };
}

window.MerkleBrowser = {
  hashMessageLeaf,
  buildConversationMerkleTree,
  deriveConversationRecordId,
  deriveConversationSegmentRecordId,
};
