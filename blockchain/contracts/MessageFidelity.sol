// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Stores Merkle roots of message digests — plaintext stays off-chain.
contract MessageFidelity {
    struct FidelityRecord {
        bytes32 contentHash;
        uint256 anchoredAt;
    }

    mapping(bytes32 => FidelityRecord) private _records;

    event HashAnchored(
        bytes32 indexed recordId,
        bytes32 contentHash,
        uint256 anchoredAt
    );

    error RecordNotFound(bytes32 recordId);

    function storeHash(bytes32 recordId, bytes32 contentHash) external {
        uint256 now_ = block.timestamp;
        _records[recordId] = FidelityRecord({
            contentHash: contentHash,
            anchoredAt: now_
        });
        emit HashAnchored(recordId, contentHash, now_);
    }

    function getHash(bytes32 recordId)
        public
        view
        returns (bytes32 contentHash, uint256 anchoredAt)
    {
        FidelityRecord storage rec = _records[recordId];
        if (rec.anchoredAt == 0) {
            revert RecordNotFound(recordId);
        }
        return (rec.contentHash, rec.anchoredAt);
    }

    function hasRecord(bytes32 recordId) external view returns (bool) {
        return _records[recordId].anchoredAt != 0;
    }

    function verifyMerkleProof(
        bytes32 leaf,
        bytes32 merkleRoot,
        bytes32[] calldata proof
    ) public pure returns (bool) {
        bytes32 computed = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 proofElement = proof[i];
            if (computed <= proofElement) {
                computed = keccak256(abi.encodePacked(computed, proofElement));
            } else {
                computed = keccak256(abi.encodePacked(proofElement, computed));
            }
        }
        return computed == merkleRoot;
    }

    function verifyMessageInHistory(
        bytes32 recordId,
        bytes32 leaf,
        bytes32[] calldata proof
    ) external view returns (bool) {
        (bytes32 merkleRoot,) = getHash(recordId);
        return verifyMerkleProof(leaf, merkleRoot, proof);
    }
}
