import { Contract, JsonRpcProvider, Wallet, type ContractTransactionResponse } from "ethers";
import type { Hex32 } from "./merkle";

export const MESSAGE_FIDELITY_ABI = [
  "function storeHash(bytes32 recordId, bytes32 contentHash)",
  "function getHash(bytes32 recordId) view returns (bytes32 contentHash, uint256 anchoredAt)",
  "function hasRecord(bytes32 recordId) view returns (bool)",
  "function verifyMerkleProof(bytes32 leaf, bytes32 merkleRoot, bytes32[] proof) pure returns (bool)",
  "function verifyMessageInHistory(bytes32 recordId, bytes32 leaf, bytes32[] proof) view returns (bool)",
  "event HashAnchored(bytes32 indexed recordId, bytes32 contentHash, uint256 anchoredAt)",
] as const;

export interface AnchorClientConfig {
  rpcUrl: string;
  contractAddress: string;
  chainId?: number;
  privateKey?: string;
}

export interface AnchorMerkleRootResult {
  recordId: Hex32;
  merkleRoot: Hex32;
  transactionHash: string;
  blockNumber: number;
  anchoredAt: number;
}

export interface VerifyOnChainResult {
  pass: boolean;
  localLeaf: Hex32;
  onChainRoot: Hex32;
  anchoredAt: number;
  contractVerified: boolean;
}

export class MessageFidelityClient {
  private readonly contract: Contract;
  private readonly provider: JsonRpcProvider;

  constructor(config: AnchorClientConfig) {
    this.provider = new JsonRpcProvider(config.rpcUrl, config.chainId ?? 11155111);
    const signerOrProvider = config.privateKey
      ? new Wallet(config.privateKey, this.provider)
      : this.provider;
    this.contract = new Contract(
      config.contractAddress,
      MESSAGE_FIDELITY_ABI,
      signerOrProvider
    );
  }

  async anchorMerkleRoot(
    recordId: Hex32,
    merkleRoot: Hex32
  ): Promise<AnchorMerkleRootResult> {
    const tx = (await this.contract.storeHash(recordId, merkleRoot)) as ContractTransactionResponse;
    const receipt = await tx.wait();
    if (!receipt) {
      throw new Error("Transaction receipt missing");
    }
    const block = await this.provider.getBlock(receipt.blockNumber);
    return {
      recordId,
      merkleRoot,
      transactionHash: receipt.hash,
      blockNumber: receipt.blockNumber,
      anchoredAt: block?.timestamp ?? 0,
    };
  }

  async getAnchoredRoot(recordId: Hex32): Promise<{ root: Hex32; anchoredAt: number }> {
    const [root, anchoredAt] = (await this.contract.getHash(recordId)) as [string, bigint];
    return { root: root as Hex32, anchoredAt: Number(anchoredAt) };
  }

  async verifyMessageInHistory(
    recordId: Hex32,
    leaf: Hex32,
    proof: Hex32[]
  ): Promise<VerifyOnChainResult> {
    const { root, anchoredAt } = await this.getAnchoredRoot(recordId);
    const contractVerified = (await this.contract.verifyMessageInHistory(
      recordId,
      leaf,
      proof
    )) as boolean;

    return {
      pass: contractVerified,
      localLeaf: leaf,
      onChainRoot: root,
      anchoredAt,
      contractVerified,
    };
  }

  static connectReadOnly(rpcUrl: string, contractAddress: string): MessageFidelityClient {
    return new MessageFidelityClient({ rpcUrl, contractAddress });
  }
}

export function createAnchorClient(config: AnchorClientConfig): MessageFidelityClient {
  return new MessageFidelityClient(config);
}

export function anchorClientFromEnv(): MessageFidelityClient {
  const rpcUrl = process.env.SEPOLIA_RPC_URL;
  const privateKey = process.env.DEPLOYER_PRIVATE_KEY;
  const contractAddress = process.env.MESSAGE_FIDELITY_ADDRESS;

  if (!rpcUrl || !privateKey || !contractAddress) {
    throw new Error(
      "Set SEPOLIA_RPC_URL, DEPLOYER_PRIVATE_KEY, and MESSAGE_FIDELITY_ADDRESS"
    );
  }

  return createAnchorClient({ rpcUrl, privateKey, contractAddress });
}

export function readOnlyClientFromEnv(): MessageFidelityClient {
  const rpcUrl = process.env.SEPOLIA_RPC_URL;
  const contractAddress = process.env.MESSAGE_FIDELITY_ADDRESS;
  if (!rpcUrl || !contractAddress) {
    throw new Error("Set SEPOLIA_RPC_URL and MESSAGE_FIDELITY_ADDRESS");
  }
  return MessageFidelityClient.connectReadOnly(rpcUrl, contractAddress);
}
