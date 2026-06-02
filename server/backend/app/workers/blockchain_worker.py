"""Backend blockchain anchor worker.

This process turns pending PostgreSQL anchor metadata into Sepolia contract
transactions. FastAPI request handlers create pending rows only; this worker is
the component that holds wallet credentials and calls the Solidity contract.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.blockchain_anchor import BlockchainAnchor
from app.repositories import blockchain_anchor_repository


MESSAGE_FIDELITY_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "recordId", "type": "bytes32"},
            {"internalType": "bytes32", "name": "contentHash", "type": "bytes32"},
        ],
        "name": "storeHash",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

LOGGER = logging.getLogger(__name__)


class BlockchainWorkerConfigError(Exception):
    """Raised when Sepolia worker configuration is incomplete."""


class BlockchainSubmissionError(Exception):
    """Raised when the contract transaction fails or reverts."""


@dataclass(frozen=True)
class AnchorSubmission:
    """Confirmed Sepolia submission metadata."""

    transaction_hash: str
    contract_address: str
    anchored_at: datetime


class MessageFidelitySubmitter:
    """Small sync wrapper around web3.py for the MessageFidelity contract."""

    def __init__(
        self,
        *,
        rpc_url: str,
        private_key: str,
        contract_address: str,
        chain_id: int,
        gas_limit: int,
        receipt_timeout_seconds: int,
    ) -> None:
        """Create the contract submitter.

        Importing web3 lazily keeps normal API imports from requiring blockchain
        runtime dependencies unless the worker process is actually started.
        """
        try:
            from web3 import Web3
        except ImportError as exc:  # pragma: no cover - depends on deployment env
            raise BlockchainWorkerConfigError(
                "web3 is not installed. Install backend requirements first."
            ) from exc

        self._web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self._web3.is_connected():
            raise BlockchainWorkerConfigError("Could not connect to Sepolia RPC URL.")

        self._account = self._web3.eth.account.from_key(private_key)
        self._contract_address = self._web3.to_checksum_address(contract_address)
        self._contract = self._web3.eth.contract(
            address=self._contract_address,
            abi=MESSAGE_FIDELITY_ABI,
        )
        self._chain_id = chain_id
        self._gas_limit = gas_limit
        self._receipt_timeout_seconds = receipt_timeout_seconds

    @classmethod
    def from_settings(cls) -> "MessageFidelitySubmitter":
        """Create a submitter from backend environment settings."""
        missing: list[str] = []
        if not settings.sepolia_rpc_url:
            missing.append("SEPOLIA_RPC_URL")
        if not settings.deployer_private_key:
            missing.append("DEPLOYER_PRIVATE_KEY")
        if not settings.message_fidelity_address:
            missing.append("MESSAGE_FIDELITY_ADDRESS")
        if missing:
            joined = ", ".join(missing)
            raise BlockchainWorkerConfigError(f"Missing blockchain settings: {joined}.")

        return cls(
            rpc_url=settings.sepolia_rpc_url,
            private_key=settings.deployer_private_key,
            contract_address=settings.message_fidelity_address,
            chain_id=settings.blockchain_worker_chain_id,
            gas_limit=settings.blockchain_worker_gas_limit,
            receipt_timeout_seconds=settings.blockchain_worker_receipt_timeout_seconds,
        )

    def submit_hash(self, record_id: str, content_hash: str) -> AnchorSubmission:
        """Write one record hash to the contract and wait for confirmation."""
        nonce = self._web3.eth.get_transaction_count(self._account.address)
        transaction = self._contract.functions.storeHash(
            record_id,
            content_hash,
        ).build_transaction(
            {
                "chainId": self._chain_id,
                "from": self._account.address,
                "gas": self._gas_limit,
                "gasPrice": self._web3.eth.gas_price,
                "nonce": nonce,
            }
        )
        signed = self._account.sign_transaction(transaction)
        raw_transaction = getattr(signed, "rawTransaction", None)
        if raw_transaction is None:
            raw_transaction = signed.raw_transaction

        tx_hash = self._web3.eth.send_raw_transaction(raw_transaction)
        receipt = self._web3.eth.wait_for_transaction_receipt(
            tx_hash,
            timeout=self._receipt_timeout_seconds,
        )
        if int(receipt.get("status", 0)) != 1:
            raise BlockchainSubmissionError(
                f"MessageFidelity.storeHash reverted: {tx_hash.hex()}"
            )

        block = self._web3.eth.get_block(receipt["blockNumber"])
        anchored_at = datetime.fromtimestamp(int(block["timestamp"]), UTC)
        return AnchorSubmission(
            transaction_hash=receipt["transactionHash"].hex(),
            contract_address=self._contract_address,
            anchored_at=anchored_at,
        )


class BlockchainAnchorWorker:
    """Poll pending backend anchors and submit them to Sepolia."""

    def __init__(
        self,
        *,
        submitter: MessageFidelitySubmitter,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
        batch_size: int | None = None,
        mark_failed_on_error: bool | None = None,
    ) -> None:
        """Create a worker bound to a DB session factory and submitter."""
        self._submitter = submitter
        self._session_factory = session_factory
        self._batch_size = batch_size or settings.blockchain_worker_batch_size
        self._mark_failed_on_error = (
            settings.blockchain_worker_mark_failed_on_error
            if mark_failed_on_error is None
            else mark_failed_on_error
        )

    async def process_pending_batch(self) -> int:
        """Process up to the configured batch size and return count handled."""
        processed = 0
        for _ in range(self._batch_size):
            if not await self.process_next_pending_anchor():
                break
            processed += 1
        return processed

    async def process_next_pending_anchor(self) -> bool:
        """Submit one pending anchor, if available.

        The pending row is selected with ``FOR UPDATE SKIP LOCKED`` and kept
        locked until the contract call either confirms or the transaction is
        rolled back, preventing duplicate submissions by parallel workers.
        """
        async with self._session_factory() as db:
            anchor = await blockchain_anchor_repository.get_next_pending_for_update(db)
            if anchor is None:
                await db.rollback()
                return False

            try:
                record_id, content_hash = _submission_values(anchor)
            except ValueError as exc:
                LOGGER.warning("Marking malformed anchor %s failed: %s", anchor.id, exc)
                await blockchain_anchor_repository.update_anchor_status(
                    db,
                    anchor.id,
                    status="failed",
                )
                await db.commit()
                return True

            try:
                submission = await asyncio.to_thread(
                    self._submitter.submit_hash,
                    record_id,
                    content_hash,
                )
            except Exception:
                if self._mark_failed_on_error:
                    LOGGER.exception("Marking anchor %s failed after submit error", anchor.id)
                    await blockchain_anchor_repository.update_anchor_status(
                        db,
                        anchor.id,
                        status="failed",
                    )
                    await db.commit()
                    return True
                await db.rollback()
                raise

            await blockchain_anchor_repository.update_anchor_status(
                db,
                anchor.id,
                status="confirmed",
                transaction_hash=submission.transaction_hash,
                contract_address=submission.contract_address,
                merkle_root=content_hash,
                anchored_at=submission.anchored_at,
            )
            await db.commit()
            LOGGER.info(
                "Confirmed blockchain anchor %s in transaction %s",
                anchor.id,
                submission.transaction_hash,
            )
            return True


def _submission_values(anchor: BlockchainAnchor) -> tuple[str, str]:
    """Return the contract record ID and hash to write for an anchor."""
    if not anchor.record_id:
        raise ValueError("record_id is missing.")

    content_hash = anchor.merkle_root or anchor.digest
    if not content_hash:
        raise ValueError("digest/merkle_root is missing.")

    return anchor.record_id, content_hash


async def run_once(
    *,
    batch_size: int | None = None,
    submitter: MessageFidelitySubmitter | None = None,
) -> int:
    """Run a one-shot backend blockchain worker batch."""
    worker = BlockchainAnchorWorker(
        submitter=submitter or MessageFidelitySubmitter.from_settings(),
        batch_size=batch_size,
    )
    return await worker.process_pending_batch()


async def run_forever(
    *,
    poll_interval_seconds: float | None = None,
    batch_size: int | None = None,
) -> None:
    """Run the worker loop until interrupted."""
    submitter = MessageFidelitySubmitter.from_settings()
    worker = BlockchainAnchorWorker(submitter=submitter, batch_size=batch_size)
    interval = poll_interval_seconds or settings.blockchain_worker_poll_interval_seconds

    while True:
        try:
            processed = await worker.process_pending_batch()
            if processed:
                LOGGER.info("Processed %s blockchain anchor(s)", processed)
        except Exception:
            LOGGER.exception("Blockchain worker batch failed")

        await asyncio.sleep(interval)


def _parse_args() -> argparse.Namespace:
    """Parse command-line flags for the worker entry point."""
    parser = argparse.ArgumentParser(description="Run the backend blockchain worker.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one batch and exit.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Maximum pending anchors to process per batch.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="Seconds to sleep between batches.",
    )
    return parser.parse_args()


async def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=settings.log_level)
    args = _parse_args()

    if args.once:
        processed = await run_once(batch_size=args.batch_size)
        LOGGER.info("Processed %s blockchain anchor(s)", processed)
        return

    await run_forever(
        poll_interval_seconds=args.poll_interval,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    asyncio.run(main())
