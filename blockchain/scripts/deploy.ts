import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

/**
 * Deploy MessageFidelity to Sepolia and write address + ABI snippet for the fidelity UI.
 *
 * Usage:
 *   cp .env.example .env   # fill SEPOLIA_RPC_URL and DEPLOYER_PRIVATE_KEY
 *   npm run deploy:sepolia
 */
async function main() {
  const [deployer] = await ethers.getSigners();
  const balance = await ethers.provider.getBalance(deployer.address);

  console.log("Deploying MessageFidelity with account:", deployer.address);
  console.log("Account balance (wei):", balance.toString());

  const factory = await ethers.getContractFactory("MessageFidelity");
  const contract = await factory.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log("MessageFidelity deployed to:", address);

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
    deployedAt: new Date().toISOString(),
    deployer: deployer.address,
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
