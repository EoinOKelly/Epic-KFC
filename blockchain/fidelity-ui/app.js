/**
 * Standalone fidelity checker: local keccak256 vs MessageFidelity on Sepolia.
 * No build step — open via `npm run serve:fidelity` so deployment.json can be fetched.
 */

const ABI = [
  "function getHash(bytes32 recordId) view returns (bytes32 contentHash, uint256 anchoredAt)",
  "function hasRecord(bytes32 recordId) view returns (bool)",
];

const $ = (id) => document.getElementById(id);

function setResult(pass, title, detail) {
  const el = $("result");
  el.classList.remove("hidden", "pass", "fail");
  el.classList.add(pass ? "pass" : "fail");
  el.textContent = pass ? `Pass — ${title}` : `Fail — ${title}`;
  if (detail) {
    $("debugOut").textContent = detail;
  }
}

function recordIdFromLabel(label) {
  return ethers.id(label.trim());
}

function localHashFromMessage(text) {
  return ethers.keccak256(ethers.toUtf8Bytes(text));
}

async function loadDeploymentFile() {
  try {
    const res = await fetch("./deployment.json");
    if (!res.ok) throw new Error("deployment.json not found — deploy first");
    const data = await res.json();
    $("contractAddress").value = data.contractAddress ?? "";
    const el = $("result");
    el.classList.remove("hidden", "pass", "fail");
    el.style.background = "rgba(61, 139, 253, 0.12)";
    el.style.border = "1px solid var(--accent)";
    el.style.color = "var(--text)";
    el.textContent = "Deployment loaded — set RPC URL, then verify.";
    $("debugOut").textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    setResult(false, "Could not load deployment.json", String(err));
  }
}

async function verifyFidelity() {
  const rpcUrl = $("rpcUrl").value.trim();
  const contractAddress = $("contractAddress").value.trim();
  const recordLabel = $("recordLabel").value.trim();
  const messageText = $("messageText").value;

  if (!rpcUrl || !contractAddress || !recordLabel) {
    setResult(false, "Missing fields", "RPC URL, contract address, and record label are required.");
    return;
  }

  const recordId = recordIdFromLabel(recordLabel);
  const localHash = localHashFromMessage(messageText);

  const debug = {
    recordLabel,
    recordId,
    localHash,
    contractAddress,
    network: "sepolia",
  };

  $("verifyBtn").disabled = true;

  try {
    const provider = new ethers.JsonRpcProvider(rpcUrl, 11155111);
    const contract = new ethers.Contract(contractAddress, ABI, provider);

    const exists = await contract.hasRecord(recordId);
    if (!exists) {
      debug.onChain = null;
      setResult(
        false,
        "No on-chain record for this ID",
        JSON.stringify(debug, null, 2)
      );
      return;
    }

    const [onChainHash, anchoredAt] = await contract.getHash(recordId);
    debug.onChainHash = onChainHash;
    debug.anchoredAt = Number(anchoredAt);
    debug.anchoredAtISO = new Date(Number(anchoredAt) * 1000).toISOString();

    const match = onChainHash.toLowerCase() === localHash.toLowerCase();
    setResult(
      match,
      match ? "Digests match" : "Digest mismatch (possible tampering)",
      JSON.stringify(debug, null, 2)
    );
  } catch (err) {
    debug.error = err.message ?? String(err);
    setResult(false, "Verification error", JSON.stringify(debug, null, 2));
  } finally {
    $("verifyBtn").disabled = false;
  }
}

$("loadDeployment").addEventListener("click", loadDeploymentFile);
$("verifyBtn").addEventListener("click", verifyFidelity);
