from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import List


ZERO_HASH = "0" * 64


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_str(data: str) -> str:
    return sha256_hex(data.encode("utf-8"))


def merkle_root(items: List[str]) -> str:
    if not items:
        return ""

    current_level = items[:]

    while len(current_level) > 1:
        next_level = []

        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            parent = sha256_str(left + right)
            next_level.append(parent)

        current_level = next_level

    return current_level[0]


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
    bits: int
    nonce: int = 0

    def serialize(self) -> str:
        return (
            f"{self.version}|"
            f"{self.previous_hash}|"
            f"{self.merkle_root}|"
            f"{self.timestamp}|"
            f"{self.bits}|"
            f"{self.nonce}"
        )

    def calculate_hash(self) -> str:
        return sha256_str(self.serialize())

    def mine(self) -> None:
        prefix = "0" * self.bits
        nonce = 0

        while True:
            self.nonce = nonce
            block_hash = self.calculate_hash()

            if block_hash.startswith(prefix):
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
        bits: int,
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
            bits=bits,
        )

        header.mine()

        return Block(
            header=header,
            transactions=transactions,
        )


class Blockchain:
    def __init__(self, bits: int = 4) -> None:
        self.bits = bits
        self.chain: List[Block] = []

    def create_genesis_block(self) -> Block:
        coinbase_tx = Transaction(
            sender="COINBASE",
            recipient="Satoshi",
            amount=50,
        )

        block = Block.create(
            version=1,
            previous_hash=ZERO_HASH,
            transactions=[coinbase_tx],
            bits=self.bits,
        )

        self.chain.append(block)
        return block

    def latest_block(self) -> Block:
        return self.chain[-1]

    def add_block(self, transactions: List[Transaction]) -> Block:
        block = Block.create(
            version=1,
            previous_hash=self.latest_block().calculate_hash(),
            transactions=transactions,
            bits=self.bits,
        )

        self.chain.append(block)
        return block

    def is_valid_chain(self) -> bool:
        prefix = "0" * self.bits

        for i, block in enumerate(self.chain):
            calculated_hash = block.calculate_hash()

            if not calculated_hash.startswith(prefix):
                print(f"[INVALID] Block {i}: hash does not satisfy difficulty")
                return False

            tx_ids = [tx.tx_id for tx in block.transactions]
            recalculated_merkle_root = merkle_root(tx_ids)

            if block.header.merkle_root != recalculated_merkle_root:
                print(f"[INVALID] Block {i}: merkle root mismatch")
                return False

            if i == 0:
                if block.header.previous_hash != ZERO_HASH:
                    print("[INVALID] Genesis block previous hash mismatch")
                    return False
            else:
                previous_block_hash = self.chain[i - 1].calculate_hash()

                if block.header.previous_hash != previous_block_hash:
                    print(f"[INVALID] Block {i}: previous hash mismatch")
                    return False

        return True

    def print_chain(self) -> None:
        for index, block in enumerate(self.chain):
            print("=" * 100)
            print(f"Block #{index}")
            print("[Header]")
            print(f"  version       : {block.header.version}")
            print(f"  previous_hash : {block.header.previous_hash}")
            print(f"  merkle_root   : {block.header.merkle_root}")
            print(f"  timestamp     : {block.header.timestamp}")
            print(f"  bits          : {block.header.bits}")
            print(f"  nonce         : {block.header.nonce}")
            print(f"  block_hash    : {block.calculate_hash()}")
            print("[Transactions]")
            for tx in block.transactions:
                print(f"  tx_id: {tx.tx_id}")
                print(f"    {tx.sender} -> {tx.recipient}: {tx.amount}")
        print("=" * 100)


def main() -> None:
    blockchain = Blockchain(bits=4)

    print("[*] Creating genesis block...")
    blockchain.create_genesis_block()

    print("[*] Mining block 1...")
    tx1 = Transaction(sender="Satoshi", recipient="Alice", amount=30)
    tx2 = Transaction(sender="Satoshi", recipient="Bob", amount=10)
    blockchain.add_block([tx1, tx2])

    print("[*] Mining block 2...")
    tx3 = Transaction(sender="Alice", recipient="Charlie", amount=5)
    tx4 = Transaction(sender="Bob", recipient="Dave", amount=2)
    tx5 = Transaction(sender="Miner1", recipient="Eve", amount=1)
    blockchain.add_block([tx3, tx4, tx5])

    print("\n[*] Current blockchain")
    blockchain.print_chain()

    print(f"\n[*] Chain valid? {blockchain.is_valid_chain()}")

    print("\n[*] Tampering with transaction data in block 1...")
    blockchain.chain[1].transactions[0].amount = 999
    blockchain.chain[1].transactions[0].finalize()

    print(f"[*] Chain valid after tampering? {blockchain.is_valid_chain()}")


if __name__ == "__main__":
    main()