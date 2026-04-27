from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import List


MAX_TARGET = int("f"*64,16)


def sha256_hex(data: bytes)->str:
    return hashlib.sha256(data).hexdigest()


def sha256_str(data:str)->str:
    return sha256_hex(data.encode())


# -----------------------------
# Real Merkle Tree
# -----------------------------
def merkle_root(tx_ids: List[str])->str:

    if not tx_ids:
        return ""

    current = tx_ids[:]

    while len(current) > 1:

        next_level=[]

        for i in range(0,len(current),2):

            left=current[i]

            if i+1 < len(current):
                right=current[i+1]
            else:
                right=left

            parent=sha256_str(left+right)
            next_level.append(parent)

        current=next_level

    return current[0]


def difficulty_to_target(difficulty:int)->int:
    return MAX_TARGET//difficulty


@dataclass
class Transaction:

    sender:str
    recipient:str
    amount:int
    tx_id:str=""

    def serialize(self):
        return f"{self.sender}->{self.recipient}:{self.amount}"

    def finalize(self):
        self.tx_id=sha256_str(self.serialize())


@dataclass
class BlockHeader:

    index:int
    previous_hash:str
    merkle_root:str
    timestamp:int
    difficulty:int
    nonce:int=0

    def serialize(self):

        return (
            f"{self.index}|"
            f"{self.previous_hash}|"
            f"{self.merkle_root}|"
            f"{self.timestamp}|"
            f"{self.difficulty}|"
            f"{self.nonce}"
        )

    def calculate_hash(self):
        return sha256_str(self.serialize())

    def hash_as_int(self):
        return int(self.calculate_hash(),16)

    def target(self):
        return difficulty_to_target(self.difficulty)

    def is_valid_pow(self):
        return self.hash_as_int() < self.target()

    def mine(self):

        nonce=0

        while True:

            self.nonce=nonce

            if self.is_valid_pow():
                return

            nonce+=1


@dataclass
class Block:

    header:BlockHeader
    transactions:List[Transaction]

    def calculate_hash(self):
        return self.header.calculate_hash()


class Blockchain:

    def __init__(
        self,
        initial_difficulty=1000,
        target_block_time=2,
        adjustment_interval=5
    ):

        self.chain=[]
        self.current_difficulty=initial_difficulty
        self.target_block_time=target_block_time
        self.adjustment_interval=adjustment_interval


    def create_genesis_block(self):

        coinbase=Transaction(
            sender="COINBASE",
            recipient="Satoshi",
            amount=50
        )

        coinbase.finalize()

        tx_ids=[coinbase.tx_id]

        root=merkle_root(tx_ids)

        header=BlockHeader(
            index=0,
            previous_hash="0"*64,
            merkle_root=root,
            timestamp=int(time.time()),
            difficulty=self.current_difficulty
        )

        header.mine()

        block=Block(
            header=header,
            transactions=[coinbase]
        )

        self.chain.append(block)
        return block


    def latest_block(self):
        return self.chain[-1]


    def adjust_difficulty_if_needed(self):

        if len(self.chain)==0:
            return

        if len(self.chain)%self.adjustment_interval!=0:
            return


        start_block=self.chain[
            len(self.chain)-self.adjustment_interval
        ]

        end_block=self.chain[-1]


        actual_time=(
            end_block.header.timestamp-
            start_block.header.timestamp
        )

        expected_time=(
            self.target_block_time*
            self.adjustment_interval
        )


        old=self.current_difficulty

        if actual_time < expected_time:
            self.current_difficulty*=2

        elif actual_time > expected_time:
            self.current_difficulty=max(
                1,
                self.current_difficulty//2
            )


        print("\n[Difficulty Adjustment]")
        print("expected:",expected_time)
        print("actual  :",actual_time)
        print("old diff:",old)
        print("new diff:",self.current_difficulty)
        print()


    def add_block(
        self,
        transactions:List[Transaction]
    ):

        self.adjust_difficulty_if_needed()

        for tx in transactions:
            tx.finalize()

        tx_ids=[
            tx.tx_id
            for tx in transactions
        ]

        # REAL MERKLE ROOT
        root=merkle_root(tx_ids)

        header=BlockHeader(
            index=len(self.chain),
            previous_hash=self.latest_block().calculate_hash(),
            merkle_root=root,
            timestamp=int(time.time()),
            difficulty=self.current_difficulty
        )

        start=time.time()
        header.mine()
        elapsed=time.time()-start

        block=Block(
            header=header,
            transactions=transactions
        )

        self.chain.append(block)

        print(
            f"Block {header.index} mined "
            f"| diff={header.difficulty} "
            f"| nonce={header.nonce} "
            f"| {elapsed:.4f}s"
        )

        return block


    def is_valid_chain(self):

        for i,block in enumerate(self.chain):

            if not block.header.is_valid_pow():
                return False


            # recalc real merkle root
            tx_ids=[
                tx.tx_id
                for tx in block.transactions
            ]

            recalculated_root=merkle_root(tx_ids)

            if recalculated_root!=block.header.merkle_root:
                print(
                    f"Merkle root mismatch block {i}"
                )
                return False


            if i>0:
                if block.header.previous_hash != \
                   self.chain[i-1].calculate_hash():
                    return False

        return True


def main():

    bc=Blockchain()

    bc.create_genesis_block()

    for i in range(1,11):

        txs=[
            Transaction(
                "Alice",
                "Bob",
                i
            ),

            Transaction(
                "Bob",
                "Charlie",
                i//2+1
            )
        ]

        bc.add_block(txs)


    print(
        "\nChain valid:",
        bc.is_valid_chain()
    )


    print("\nTampering tx...")

    bc.chain[2].transactions[0].amount=999
    bc.chain[2].transactions[0].finalize()

    print(
        "Chain valid after tamper:",
        bc.is_valid_chain()
    )


if __name__=="__main__":
    main()