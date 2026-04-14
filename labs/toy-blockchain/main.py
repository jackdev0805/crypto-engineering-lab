from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import List


ZERO_HASH = "0" * 64


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Block:
    index: int
    timestamp: int
    data: str
    previous_hash: str
    nonce: int = 0
    hash: str = ""

    def header_without_nonce(self) -> bytes:
        """
        nonce를 제외한 블록의 '고정된' 부분이다.
        채굴 중에는 보통 nonce만 바뀌고 나머지 필드는 같은 후보 블록으로 유지된다.
        """
        header = f"{self.index}|{self.timestamp}|{self.data}|{self.previous_hash}|"
        return header.encode("utf-8")

    def calculate_hash(self) -> str:
        """
        현재 nonce를 포함해서 블록 해시를 계산한다.
        """
        return self.calculate_hash_with_nonce(self.nonce)

    def calculate_hash_with_nonce(self, nonce: int) -> str:
        base = self.header_without_nonce()
        return sha256_hex(base + str(nonce).encode("utf-8"))

    def mine(self, difficulty: int) -> None:
        """
        학습용 PoW:
        해시 문자열이 특정 개수의 '0'으로 시작할 때까지 nonce를 증가시킨다.

        실제 비트코인은 '문자열이 0000으로 시작하냐'를 직접 보는 게 아니라,
        block header의 이중 SHA-256 결과를 정수로 보고, 그것이 target보다 작은지 검사한다.
        여기서는 그 개념을 쉽게 보여주기 위해 prefix 방식으로 단순화했다.
        """
        if difficulty < 1:
            raise ValueError("difficulty must be >= 1")

        prefix = "0" * difficulty
        nonce = 0

        while True:
            current_hash = self.calculate_hash_with_nonce(nonce)

            if current_hash.startswith(prefix):
                self.nonce = nonce
                self.hash = current_hash
                return

            nonce += 1


class Blockchain:
    def __init__(self, difficulty: int = 4) -> None:
        if difficulty < 1:
            raise ValueError("difficulty must be >= 1")

        self.difficulty = difficulty
        self.chain: List[Block] = [self.create_genesis_block()]

    def create_genesis_block(self) -> Block:
        genesis = Block(
            index=0,
            timestamp=int(time.time()),
            data="Genesis Block",
            previous_hash=ZERO_HASH,
        )
        genesis.mine(self.difficulty)
        return genesis

    def latest_block(self) -> Block:
        return self.chain[-1]

    def add_block(self, data: str) -> Block:
        prev = self.latest_block()

        block = Block(
            index=prev.index + 1,
            timestamp=int(time.time()),
            data=data,
            previous_hash=prev.hash,
        )
        block.mine(self.difficulty)
        self.chain.append(block)
        return block

    def is_valid(self) -> bool:
        prefix = "0" * self.difficulty

        # genesis block 검증
        genesis = self.chain[0]
        if genesis.previous_hash != ZERO_HASH:
            print("[INVALID] Genesis block previous_hash is not ZERO_HASH")
            return False

        if genesis.hash != genesis.calculate_hash():
            print("[INVALID] Genesis block stored hash mismatch")
            return False

        if not genesis.hash.startswith(prefix):
            print("[INVALID] Genesis block does not satisfy difficulty")
            return False

        # 나머지 블록 검증
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            recalculated_hash = current.calculate_hash()

            if current.hash != recalculated_hash:
                print(f"[INVALID] Block {current.index}: stored hash mismatch")
                return False

            if not current.hash.startswith(prefix):
                print(f"[INVALID] Block {current.index}: does not satisfy difficulty")
                return False

            if current.previous_hash != previous.hash:
                print(f"[INVALID] Block {current.index}: previous_hash mismatch")
                return False

        return True

    def print_chain(self) -> None:
        for block in self.chain:
            print("=" * 100)
            print(f"index         : {block.index}")
            print(f"timestamp     : {block.timestamp}")
            print(f"data          : {block.data}")
            print(f"previous_hash : {block.previous_hash}")
            print(f"nonce         : {block.nonce}")
            print(f"hash          : {block.hash}")
        print("=" * 100)


def main() -> None:
    blockchain = Blockchain(difficulty=5)

    print("[*] Mining block 1...")
    blockchain.add_block("Alice -> Bob : 10 coins")

    print("[*] Mining block 2...")
    blockchain.add_block("Bob -> Charlie : 3 coins")

    print("[*] Mining block 3...")
    blockchain.add_block("Charlie -> Dave : 1 coin")

    print("\n[*] Current chain")
    blockchain.print_chain()

    print(f"\n[*] Chain valid? {blockchain.is_valid()}")

    print("\n[*] Tampering block 1 data...")
    blockchain.chain[1].data = "Alice -> Bob : 1000 coins"

    print(f"[*] Chain valid after tampering? {blockchain.is_valid()}")


if __name__ == "__main__":
    main()