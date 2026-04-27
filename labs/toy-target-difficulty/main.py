from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass


MAX_TARGET = int("f" * 64, 16)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_str(data: str) -> str:
    return sha256_hex(data.encode("utf-8"))


def difficulty_to_target(difficulty: int) -> int:
    if difficulty < 1:
        raise ValueError("difficulty must be >= 1")

    return MAX_TARGET // difficulty


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


def print_mining_result(header: BlockHeader) -> None:
    block_hash = header.calculate_hash()
    hash_int = int(block_hash, 16)
    target = header.target()

    print("=" * 100)
    print(f"difficulty : {header.difficulty}")
    print(f"nonce      : {header.nonce}")
    print(f"hash       : {block_hash}")
    print(f"hash int   : {hash_int}")
    print(f"target     : {target}")
    print(f"valid pow  : {hash_int < target}")
    print("=" * 100)


def main() -> None:
    previous_hash = "0" * 64
    merkle_root = sha256_str("tx1|tx2|tx3")

    for difficulty in [1, 10, 100, 1000, 10000]:
        header = BlockHeader(
            version=1,
            previous_hash=previous_hash,
            merkle_root=merkle_root,
            timestamp=int(time.time()),
            difficulty=difficulty,
        )

        print(f"\n[*] Mining with difficulty={difficulty}...")
        header.mine()
        print_mining_result(header)


if __name__ == "__main__":
    main()