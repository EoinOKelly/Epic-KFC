import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  const [deployer] = await ethers.getSigners();
  const balance = await ethers.provider.getBalance(deployer.address);

  console.log("Deploying MessageFidelity with account:", deployer.address);
  console.log("Account balance (wei):", balance.toString());

  const factory = await ethers.getContractFactory("MessageFidelity");
  const contract = await factory.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  const contractOwner = await contract.owner();
  console.log("MessageFidelity deployed to:", address);
  console.log("Contract owner (only this address may storeHash):", contractOwner);

  const artifactPath = path.join(
    __dirname,
    "..",
    "artifacts",
    "contracts",
    "MessageFidelity.sol",
    "MessageFidelity.json"
  );
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8")) as {
    abi: unknown;
  };

  const outDir = path.join(__dirname, "..", "fidelity-ui");
  fs.mkdirSync(outDir, { recursive: true });

  const deployment = {
    network: "sepolia",
    chainId: 11155111,
    contractAddress: address,
    messageFidelityAddress: address,
    deployedAt: new Date().toISOString(),
    deployer: deployer.address,
    owner: contractOwner,
    contractVersion: "owner-write-once-v1",
    envHint: "MESSAGE_FIDELITY_ADDRESS in .env; anchors need owner DEPLOYER_PRIVATE_KEY",
  };

  fs.writeFileSync(
    path.join(outDir, "deployment.json"),
    JSON.stringify(deployment, null, 2)
  );
  fs.writeFileSync(
    path.join(outDir, "MessageFidelity.abi.json"),
    JSON.stringify(artifact.abi, null, 2)
  );

  console.log("Wrote fidelity-ui/deployment.json and MessageFidelity.abi.json");
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
