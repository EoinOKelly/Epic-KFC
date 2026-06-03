const ABI = [
  "function getHash(bytes32 recordId) view returns (bytes32 contentHash, uint256 anchoredAt)",
  "function verifyMessageInHistory(bytes32 recordId, bytes32 leaf, bytes32[] proof) view returns (bool)",
];

const $ = (id) => document.getElementById(id);

function setResult(pass, title, detail) {
  const el = $("result");
  el.classList.remove("hidden", "pass", "fail");
  el.classList.add(pass ? "pass" : "fail");
  el.textContent = pass ? `Pass: ${title}` : `Fail: ${title}`;
  if (detail) $("debugOut").textContent = detail;
}

async function loadDeploymentFile() {
  try {
    const res = await fetch("./deployment.json");
    if (!res.ok) throw new Error("deployment.json not found; run npm run deploy:sepolia");
    const data = await res.json();
    $("contractAddress").value = data.contractAddress ?? "";
    const el = $("result");
    el.classList.remove("hidden", "pass", "fail");
    el.style.background = "rgba(61, 139, 253, 0.12)";
    el.style.border = "1px solid var(--accent)";
    el.style.color = "var(--text)";
    el.textContent = "Deployment loaded. Set RPC URL and verify.";
    $("debugOut").textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    setResult(false, "Could not load deployment.json", String(err));
  }
}

async function verifyMerkleFidelity() {
  const rpcUrl = $("rpcUrl").value.trim();
  const contractAddress = $("contractAddress").value.trim();
  const userA = $("userA").value.trim();
  const userB = $("userB").value.trim();
  const verifyMessageId = $("verifyMessageId").value.trim();

  let messages;
  try {
    messages = JSON.parse($("messagesJson").value);
    if (!Array.isArray(messages) || messages.length === 0) throw new Error("Need a non-empty array");
  } catch (err) {
    setResult(false, "Invalid messages JSON", String(err));
    return;
  }

  if (!rpcUrl || !contractAddress || !userA || !userB || !verifyMessageId) {
    setResult(false, "Missing fields", "Fill RPC, contract, both user IDs, and message ID to verify.");
    return;
  }

  const target = messages.find((m) => m.messageId === verifyMessageId);
  if (!target) {
    setResult(false, "Message not in JSON list", verifyMessageId);
    return;
  }

  $("verifyBtn").disabled = true;

  try {
    const tree = MerkleBrowser.buildConversationMerkleTree(messages);
    const segmentKey = $("segmentKey").value.trim() || String(messages.length);
    const recordId = MerkleBrowser.deriveConversationSegmentRecordId(
      userA,
      userB,
      segmentKey
    );
    const leaf = MerkleBrowser.hashMessageLeaf(target.messageId, target.plaintext);
    const proof = tree.getProofForMessage(verifyMessageId);

    const provider = new ethers.JsonRpcProvider(rpcUrl, 11155111);
    const contract = new ethers.Contract(contractAddress, ABI, provider);
    const [onChainRoot, anchoredAt] = await contract.getHash(recordId);
    const contractOk = await contract.verifyMessageInHistory(recordId, leaf, proof);

    const localRootMatch = tree.root.toLowerCase() === onChainRoot.toLowerCase();
    const pass = contractOk && localRootMatch;

    const debug = {
      recordId,
      localMerkleRoot: tree.root,
      onChainRoot,
      anchoredAt: Number(anchoredAt),
      anchoredAtISO: new Date(Number(anchoredAt) * 1000).toISOString(),
      verifiedMessageId: verifyMessageId,
      leaf,
      proof,
      contractVerified: contractOk,
      rootMatches: localRootMatch,
    };

    setResult(
      pass,
      pass
        ? "Message proven in anchored Merkle history"
        : "Proof or root mismatch (possible tampering)",
      JSON.stringify(debug, null, 2)
    );
  } catch (err) {
    setResult(false, "Verification error", err.message ?? String(err));
  } finally {
    $("verifyBtn").disabled = false;
  }
}

$("loadDeployment").addEventListener("click", loadDeploymentFile);
$("verifyBtn").addEventListener("click", verifyMerkleFidelity);
