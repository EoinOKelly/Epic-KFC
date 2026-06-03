import { expect } from "chai";
import { ethers } from "hardhat";
import { MessageFidelity } from "../typechain-types";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";

describe("MessageFidelity", () => {
  let fidelity: MessageFidelity;
  let owner: HardhatEthersSigner;
  let other: HardhatEthersSigner;

  const recordId = ethers.id("conversation:alice-bob");
  const contentHash = ethers.keccak256(ethers.toUtf8Bytes("hello, integrity"));

  beforeEach(async () => {
    [owner, other] = await ethers.getSigners();
    fidelity = await ethers.deployContract("MessageFidelity");
  });

  it("sets deployer as owner", async () => {
    expect(await fidelity.owner()).to.equal(owner.address);
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

  it("reverts when a non-owner stores a hash", async () => {
    await expect(
      fidelity.connect(other).storeHash(recordId, contentHash)
    ).to.be.revertedWithCustomError(fidelity, "UnauthorizedWriter");
  });

  it("reverts when overwriting an existing record", async () => {
    const updated = ethers.keccak256(ethers.toUtf8Bytes("tampered?"));
    await fidelity.storeHash(recordId, contentHash);

    await expect(fidelity.storeHash(recordId, updated))
      .to.be.revertedWithCustomError(fidelity, "RecordAlreadyAnchored")
      .withArgs(recordId);

    const [storedHash] = await fidelity.getHash(recordId);
    expect(storedHash).to.equal(contentHash);
  });
});
