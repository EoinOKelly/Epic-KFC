import { ethers } from "hardhat";

/**
 * Anchor a message digest on Sepolia (demo / integration helper).
 *
 *   npx hardhat run scripts/anchor.ts --network sepolia -- \
 *     --contract 0xYourAddress --label "conversation:alice-bob" --message "hello"
 */
async function main() {
  const args = process.argv.slice(2);
  const getArg = (flag: string) => {
    const i = args.indexOf(flag);
    return i >= 0 ? args[i + 1] : undefined;
  };

  const contractAddress = getArg("--contract") ?? process.env.MESSAGE_FIDELITY_ADDRESS;
  const label = getArg("--label");
  const message = getArg("--message");

  if (!contractAddress || !label || message === undefined) {
    throw new Error(
      "Usage: --contract <addr> --label <recordIdLabel> --message <text>"
    );
  }

  const recordId = ethers.id(label);
  const contentHash = ethers.keccak256(ethers.toUtf8Bytes(message));

  const fidelity = await ethers.getContractAt("MessageFidelity", contractAddress);
  const tx = await fidelity.storeHash(recordId, contentHash);
  console.log("Tx:", tx.hash);
  await tx.wait();
  console.log("Anchored", { recordId, contentHash });
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
