import { expect } from "chai";
import { ethers } from "hardhat";
import { MessageFidelity } from "../typechain-types";

describe("MessageFidelity", () => {
  let fidelity: MessageFidelity;

  const recordId = ethers.id("conversation:alice-bob");
  const contentHash = ethers.keccak256(ethers.toUtf8Bytes("hello, integrity"));

  beforeEach(async () => {
    fidelity = await ethers.deployContract("MessageFidelity");
  });

  it("stores and retrieves a hash with timestamp", async () => {
    const tx = await fidelity.storeHash(recordId, contentHash);
    const receipt = await tx.wait();
    const block = await ethers.provider.getBlock(receipt!.blockNumber!);

    const [storedHash, anchoredAt] = await fidelity.getHash(recordId);
    expect(storedHash).to.equal(contentHash);
    expect(anchoredAt).to.equal(block!.timestamp);
  });

  it("reverts when record is missing", async () => {
    await expect(fidelity.getHash(recordId)).to.be.revertedWithCustomError(
      fidelity,
      "RecordNotFound"
    );
  });

  it("updates an existing record", async () => {
    const updated = ethers.keccak256(ethers.toUtf8Bytes("tampered?"));
    await fidelity.storeHash(recordId, contentHash);
    await fidelity.storeHash(recordId, updated);

    const [storedHash] = await fidelity.getHash(recordId);
    expect(storedHash).to.equal(updated);
  });
});
