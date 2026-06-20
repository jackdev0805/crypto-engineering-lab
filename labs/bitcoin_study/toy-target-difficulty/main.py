from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import List


MAX_TARGET = int("f" * 64, 16)
ZERO_HASH = "0" * 64


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_str(data: str) -> str:
    return sha256_hex(data.encode("utf-8"))


def merkle_root(tx_ids: List[str]) -> str:
    if not tx_ids:
        return ""

    current_level = tx_ids[:]

    while len(current_level) > 1:
        next_level = []

        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            parent = sha256_str(left + right)
            next_level.append(parent)

        current_level = next_level

    return current_level[0]


def difficulty_to_target(difficulty: int) -> int:
    if difficulty < 1:
        raise ValueError("difficulty must be >= 1")

    return MAX_TARGET // difficulty


@dataclass
class Transaction:
    sender: str
    recipient: str
    amount: int
    tx_id: str = ""

    def serialize(self) -> str:
        return f"{self.sender}->{self.recipient}:{self.amount}"

    def finalize(self) -> None:
        self.tx_id = sha256_str(self.serialize())


@dataclass
class BlockHeader:
    version: int
    previous_hash: str
    merkle_root: str
    timestamp: int
    difficulty: int
    nonce: int = 0

    def serialize(self) -> str:
        return (
            f"{self.version}|"
            f"{self.previous_hash}|"
            f"{self.merkle_root}|"
            f"{self.timestamp}|"
            f"{self.difficulty}|"
            f"{self.nonce}"
        )

    def calculate_hash(self) -> str:
        return sha256_str(self.serialize())

    def calculate_hash_as_int(self) -> int:
        return int(self.calculate_hash(), 16)

    def target(self) -> int:
        return difficulty_to_target(self.difficulty)

    def is_valid_pow(self) -> bool:
        return self.calculate_hash_as_int() < self.target()

    def mine(self) -> None:
        nonce = 0

        while True:
            self.nonce = nonce

            if self.is_valid_pow():
                return

            nonce += 1


@dataclass
class Block:
    header: BlockHeader
    transactions: List[Transaction]

    def calculate_hash(self) -> str:
        return self.header.calculate_hash()

    @staticmethod
    def create(
        version: int,
        previous_hash: str,
        transactions: List[Transaction],
        difficulty: int,
    ) -> "Block":
        for tx in transactions:
            if not tx.tx_id:
                tx.finalize()

        tx_ids = [tx.tx_id for tx in transactions]
        root = merkle_root(tx_ids)

        header = BlockHeader(
            version=version,
            previous_hash=previous_hash,
            merkle_root=root,
            timestamp=int(time.time()),
            difficulty=difficulty,
        )

        header.mine()

        return Block(
            header=header,
            transactions=transactions,
        )


def print_mining_result(block: Block) -> None:
    block_hash = block.calculate_hash()
    hash_int = int(block_hash, 16)
    target = block.header.target()

    print("=" * 100)
    print(f"difficulty  : {block.header.difficulty}")
    print(f"nonce       : {block.header.nonce}")
    print(f"merkle_root : {block.header.merkle_root}")
    print(f"hash        : {block_hash}")
    print(f"hash int    : {hash_int}")
    print(f"target      : {target}")
    print(f"valid pow   : {hash_int < target}")
    print("[Transactions]")
    for tx in block.transactions:
        print(f"  {tx.tx_id} | {tx.sender} -> {tx.recipient}: {tx.amount}")
    print("=" * 100)


def main() -> None:
    previous_hash = ZERO_HASH

    transactions = [
        Transaction(sender="Satoshi", recipient="Alice", amount=30),
        Transaction(sender="Alice", recipient="Bob", amount=10),
        Transaction(sender="Bob", recipient="Charlie", amount=4),
    ]

    for difficulty in [1, 10, 100, 1000, 10000]:
        print(f"\n[*] Mining with difficulty={difficulty}...")

        block = Block.create(
            version=1,
            previous_hash=previous_hash,
            transactions=transactions,
            difficulty=difficulty,
        )

        print_mining_result(block)

    print("\n[*] Tampering test...")
    block = Block.create(
        version=1,
        previous_hash=previous_hash,
        transactions=transactions,
        difficulty=1000,
    )

    original_root = block.header.merkle_root
    original_hash = block.calculate_hash()

    block.transactions[1].amount = 999
    block.transactions[1].finalize()

    recalculated_root = merkle_root([tx.tx_id for tx in block.transactions])

    print(f"original merkle root    : {original_root}")
    print(f"recalculated merkle root: {recalculated_root}")
    print(f"original block hash     : {original_hash}")
    print(f"merkle root changed?    : {original_root != recalculated_root}")


if __name__ == "__main__":
    main()