// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title MessageFidelity
 * @notice Anchors keccak256 digests of messaging data on-chain for tamper-evident verification.
 *
 * @dev Design notes (CS4455 Epic Messaging — blockchain integrity module):
 *      - Only the 32-byte keccak256 digest is stored on-chain, never plaintext messages.
 *      - `recordId` is an opaque identifier (conversation ID, message ID, or digest of a label).
 *        Callers should pass `bytes32` values; off-chain tools can derive them with keccak256(utf8Bytes(...)).
 *      - `block.timestamp` is captured at write time as an auditable anchor (not a consensus clock).
 *      - Gas: single SSTORE for new keys; updates reuse the same slot. Custom errors save bytecode vs strings.
 */
contract MessageFidelity {
    /// @notice On-chain anchor for one logical record (conversation or message).
    struct FidelityRecord {
        bytes32 contentHash;
        uint256 anchoredAt;
    }

    /// @dev recordId => anchored digest + timestamp
    mapping(bytes32 => FidelityRecord) private _records;

    /// @notice Emitted when a digest is stored or updated (indexable by integrators/backends).
    event HashAnchored(
        bytes32 indexed recordId,
        bytes32 contentHash,
        uint256 anchoredAt
    );

    error RecordNotFound(bytes32 recordId);

    /**
     * @notice Store or update the keccak256 digest for `recordId`.
     * @param recordId Opaque conversation or message identifier (bytes32).
     * @param contentHash keccak256 digest of the off-chain payload or conversation digest.
     */
    function storeHash(bytes32 recordId, bytes32 contentHash) external {
        uint256 now_ = block.timestamp;
        _records[recordId] = FidelityRecord({
            contentHash: contentHash,
            anchoredAt: now_
        });
        emit HashAnchored(recordId, contentHash, now_);
    }

    /**
     * @notice Retrieve the anchored digest and timestamp for `recordId`.
     * @return contentHash The stored keccak256 digest.
     * @return anchoredAt Unix timestamp when the digest was last written.
     */
    function getHash(bytes32 recordId)
        external
        view
        returns (bytes32 contentHash, uint256 anchoredAt)
    {
        FidelityRecord storage rec = _records[recordId];
        if (rec.anchoredAt == 0) {
            revert RecordNotFound(recordId);
        }
        return (rec.contentHash, rec.anchoredAt);
    }

    /**
     * @notice Lightweight existence check without reverting (useful for UIs and backends).
     */
    function hasRecord(bytes32 recordId) external view returns (bool) {
        return _records[recordId].anchoredAt != 0;
    }
}
