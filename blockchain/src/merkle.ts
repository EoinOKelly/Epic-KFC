import { ethers } from "ethers";

export type Hex32 = `0x${string}`;

export function hashMessageLeaf(messageId: string, plaintext: string): Hex32 {
  const payloadHash = ethers.keccak256(ethers.toUtf8Bytes(plaintext));
  return ethers.keccak256(
    ethers.solidityPacked(["string", "bytes32"], [messageId, payloadHash])
  ) as Hex32;
}

// Sorted pair hash — must match MessageFidelity.sol
export function hashPair(left: Hex32, right: Hex32): Hex32 {
  const a = left.toLowerCase() as Hex32;
  const b = right.toLowerCase() as Hex32;
  const [first, second] = a <= b ? [a, b] : [b, a];
  return ethers.keccak256(
    ethers.solidityPacked(["bytes32", "bytes32"], [first, second])
  ) as Hex32;
}

export interface MerkleTreeBuildResult {
  root: Hex32;
  leaves: Hex32[];
  getProof: (leafIndex: number) => Hex32[];
  verifyProof: (leaf: Hex32, proof: Hex32[]) => boolean;
}

export function buildMerkleTree(leaves: Hex32[]): MerkleTreeBuildResult {
  if (leaves.length === 0) {
    throw new Error("Merkle tree requires at least one message leaf");
  }

  const layers: Hex32[][] = [leaves.map((l) => l.toLowerCase() as Hex32)];

  while (layers[layers.length - 1].length > 1) {
    const current = layers[layers.length - 1];
    const next: Hex32[] = [];
    for (let i = 0; i < current.length; i += 2) {
      if (i + 1 < current.length) {
        next.push(hashPair(current[i], current[i + 1]));
      } else {
        next.push(hashPair(current[i], current[i]));
      }
    }
    layers.push(next);
  }

  const root = layers[layers.length - 1][0];

  function getProof(leafIndex: number): Hex32[] {
    if (leafIndex < 0 || leafIndex >= leaves.length) {
      throw new Error(`Leaf index out of range: ${leafIndex}`);
    }
    const proof: Hex32[] = [];
    let index = leafIndex;
    for (let layer = 0; layer < layers.length - 1; layer += 1) {
      const layerNodes = layers[layer];
      const siblingIndex = index % 2 === 0 ? index + 1 : index - 1;
      if (siblingIndex < layerNodes.length) {
        proof.push(layerNodes[siblingIndex]);
      } else {
        proof.push(layerNodes[index]);
      }
      index = Math.floor(index / 2);
    }
    return proof;
  }

  function verifyProof(leaf: Hex32, proof: Hex32[]): boolean {
    let computed = leaf.toLowerCase() as Hex32;
    for (const sibling of proof) {
      computed = hashPair(computed, sibling.toLowerCase() as Hex32);
    }
    return computed.toLowerCase() === root.toLowerCase();
  }

  return { root, leaves: layers[0], getProof, verifyProof };
}

export function verifyMerkleProof(
  root: Hex32,
  leaf: Hex32,
  proof: Hex32[]
): boolean {
  let computed = leaf.toLowerCase() as Hex32;
  for (const sibling of proof) {
    computed = hashPair(computed, sibling.toLowerCase() as Hex32);
  }
  return computed.toLowerCase() === root.toLowerCase();
}
