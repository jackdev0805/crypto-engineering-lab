from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


ZERO_HASH = "0" * 64
MAX_TARGET = int("f" * 64, 16)


def sha256_str(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def merkle_root(tx_ids: List[str]) -> str:
    if not tx_ids:
        return ""

    level = tx_ids[:]

    while len(level) > 1:
        next_level = []

        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            next_level.append(sha256_str(left + right))

        level = next_level

    return level[0]


def difficulty_to_target(difficulty: int) -> int:
    if difficulty < 1:
        raise ValueError("difficulty must be >= 1")
    return MAX_TARGET // difficulty


@dataclass
class TransactionInput:
    prev_tx_id: str
    output_index: int

    def key(self) -> str:
        return f"{self.prev_tx_id}:{self.output_index}"


@dataclass
class TransactionOutput:
    recipient: str
    amount: int


@dataclass
class Transaction:
    inputs: List[TransactionInput]
    outputs: List[TransactionOutput]
    fee: int
    meta: str
    tx_id: str = ""

    def serialize(self) -> str:
        ins = "|".join(i.key() for i in self.inputs)
        outs = "|".join(f"{o.recipient}:{o.amount}" for o in self.outputs)
        return f"IN[{ins}]OUT[{outs}]FEE[{self.fee}]META[{self.meta}]"

    def finalize(self) -> None:
        self.tx_id = sha256_str(self.serialize())

    @staticmethod
    def coinbase(recipient: str, amount: int, meta: str) -> "Transaction":
        tx = Transaction(
            inputs=[],
            outputs=[TransactionOutput(recipient=recipient, amount=amount)],
            fee=0,
            meta=meta,
        )
        tx.finalize()
        return tx


@dataclass
class UTXO:
    tx_id: str
    output_index: int
    recipient: str
    amount: int

    def key(self) -> str:
        return f"{self.tx_id}:{self.output_index}"


class UTXOSet:
    def __init__(self) -> None:
        self.utxos: Dict[str, UTXO] = {}

    def copy(self) -> "UTXOSet":
        copied = UTXOSet()
        copied.utxos = dict(self.utxos)
        return copied

    def add(self, utxo: UTXO) -> None:
        self.utxos[utxo.key()] = utxo

    def get(self, tx_input: TransactionInput) -> Optional[UTXO]:
        return self.utxos.get(tx_input.key())

    def remove(self, tx_input: TransactionInput) -> None:
        del self.utxos[tx_input.key()]

    def all_for_recipient(self, recipient: str) -> List[UTXO]:
        return [u for u in self.utxos.values() if u.recipient == recipient]

    def balance_of(self, recipient: str) -> int:
        return sum(u.amount for u in self.all_for_recipient(recipient))


@dataclass
class BlockHeader:
    height: int
    previous_hash: str
    merkle_root: str
    timestamp: int
    miner: str
    difficulty: int
    nonce: int = 0

    def serialize(self) -> str:
        return (
            f"{self.height}|{self.previous_hash}|{self.merkle_root}|"
            f"{self.timestamp}|{self.miner}|{self.difficulty}|{self.nonce}"
        )

    def hash(self) -> str:
        return sha256_str(self.serialize())

    def hash_as_int(self) -> int:
        return int(self.hash(), 16)

    def target(self) -> int:
        return difficulty_to_target(self.difficulty)

    def work(self) -> int:
        """
        학습용 block work.

        실제 비트코인은 target 기반으로 더 정교하게 계산하지만,
        이 예제에서는 difficulty 자체를 해당 블록이 대표하는 작업량으로 본다.
        """
        return self.difficulty

    def is_valid_pow(self) -> bool:
        return self.hash_as_int() < self.target()

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

    def hash(self) -> str:
        return self.header.hash()

    def work(self) -> int:
        return self.header.work()


class Wallet:
    def __init__(self, owner: str) -> None:
        self.owner = owner

    def create_transaction(
        self,
        visible_utxo_set: UTXOSet,
        recipient: str,
        amount: int,
        fee: int,
        meta: str,
    ) -> Transaction:
        my_utxos = visible_utxo_set.all_for_recipient(self.owner)

        selected: List[UTXO] = []
        total = 0

        for utxo in my_utxos:
            selected.append(utxo)
            total += utxo.amount
            if total >= amount + fee:
                break

        if total < amount + fee:
            raise ValueError(f"{self.owner} has insufficient balance")

        inputs = [
            TransactionInput(prev_tx_id=u.tx_id, output_index=u.output_index)
            for u in selected
        ]

        outputs = [TransactionOutput(recipient=recipient, amount=amount)]

        change = total - amount - fee
        if change > 0:
            outputs.append(TransactionOutput(recipient=self.owner, amount=change))

        tx = Transaction(inputs=inputs, outputs=outputs, fee=fee, meta=meta)
        tx.finalize()
        return tx


class Miner:
    def __init__(self, name: str, difficulty: int) -> None:
        self.name = name
        self.difficulty = difficulty

    def mine_block(self, node: "Node", max_txs: int = 10) -> Block:
        selected: List[Transaction] = []
        temp_utxo = node.utxo_set.copy()

        candidates = sorted(
            node.mempool.values(),
            key=lambda tx: tx.fee,
            reverse=True,
        )

        for tx in candidates:
            if len(selected) >= max_txs:
                break

            if node.validate_transaction(tx, temp_utxo):
                selected.append(tx)
                node.apply_transaction(tx, temp_utxo)

        total_fees = sum(tx.fee for tx in selected)

        coinbase = Transaction.coinbase(
            recipient=self.name,
            amount=node.block_reward + total_fees,
            meta=f"coinbase-{self.name}-height-{node.height()}",
        )

        block_txs = [coinbase] + selected
        root = merkle_root([tx.tx_id for tx in block_txs])

        header = BlockHeader(
            height=node.height(),
            previous_hash=node.tip_hash(),
            merkle_root=root,
            timestamp=int(time.time()),
            miner=self.name,
            difficulty=self.difficulty,
        )
        header.mine()

        return Block(header=header, transactions=block_txs)


class Node:
    def __init__(self, name: str, block_reward: int = 50):
        self.name = name
        self.block_reward = block_reward
        self.chain: List[Block] = []
        self.utxo_set = UTXOSet()
        self.mempool: Dict[str, Transaction] = {}

    def height(self) -> int:
        return len(self.chain)

    def tip_hash(self) -> str:
        if not self.chain:
            return ZERO_HASH
        return self.chain[-1].hash()

    def total_work(self, chain: Optional[List[Block]] = None) -> int:
        target_chain = chain if chain is not None else self.chain
        return sum(block.work() for block in target_chain)

    def clone_from(self, other: "Node") -> None:
        self.chain = list(other.chain)
        self.utxo_set = other.utxo_set.copy()
        self.mempool = dict(other.mempool)

    def create_genesis_block(self) -> None:
        coinbase = Transaction.coinbase(
            recipient="Satoshi",
            amount=self.block_reward,
            meta="genesis",
        )

        root = merkle_root([coinbase.tx_id])

        header = BlockHeader(
            height=0,
            previous_hash=ZERO_HASH,
            merkle_root=root,
            timestamp=int(time.time()),
            miner="genesis",
            difficulty=1,
        )
        header.mine()

        block = Block(header=header, transactions=[coinbase])
        self.chain.append(block)
        self.apply_block(block)

    def validate_transaction(self, tx: Transaction, utxo_set: UTXOSet) -> bool:
        if not tx.outputs:
            return False

        for output in tx.outputs:
            if output.amount <= 0:
                return False

        if not tx.inputs:
            return True

        seen = set()
        total_input = 0

        for tx_input in tx.inputs:
            if tx_input.key() in seen:
                return False
            seen.add(tx_input.key())

            utxo = utxo_set.get(tx_input)
            if utxo is None:
                return False

            total_input += utxo.amount

        total_output = sum(o.amount for o in tx.outputs)

        return total_input >= total_output + tx.fee

    def apply_transaction(self, tx: Transaction, utxo_set: UTXOSet) -> None:
        for tx_input in tx.inputs:
            utxo_set.remove(tx_input)

        for index, output in enumerate(tx.outputs):
            utxo_set.add(
                UTXO(
                    tx_id=tx.tx_id,
                    output_index=index,
                    recipient=output.recipient,
                    amount=output.amount,
                )
            )

    def apply_block(self, block: Block) -> None:
        for tx in block.transactions:
            self.apply_transaction(tx, self.utxo_set)

    def submit_transaction(self, tx: Transaction) -> bool:
        if not self.validate_transaction(tx, self.utxo_set):
            print(f"[{self.name}] reject invalid tx {tx.meta}")
            return False

        new_inputs = {i.key() for i in tx.inputs}

        for existing_tx in self.mempool.values():
            existing_inputs = {i.key() for i in existing_tx.inputs}
            if new_inputs & existing_inputs:
                print(f"[{self.name}] reject mempool conflict tx {tx.meta}")
                return False

        self.mempool[tx.tx_id] = tx
        print(f"[{self.name}] accept tx {tx.meta}")
        return True

    def validate_chain(self, chain: List[Block]) -> bool:
        temp_utxo = UTXOSet()

        for index, block in enumerate(chain):
            if not block.header.is_valid_pow():
                return False

            recalculated_root = merkle_root([tx.tx_id for tx in block.transactions])
            if recalculated_root != block.header.merkle_root:
                return False

            if index == 0:
                if block.header.previous_hash != ZERO_HASH:
                    return False
            else:
                if block.header.previous_hash != chain[index - 1].hash():
                    return False

            for tx in block.transactions:
                if not self.validate_transaction(tx, temp_utxo):
                    return False
                self.apply_transaction(tx, temp_utxo)

        return True

    def rebuild_utxo_from_chain(self, chain: List[Block]) -> UTXOSet:
        utxo_set = UTXOSet()

        for block in chain:
            for tx in block.transactions:
                if not self.validate_transaction(tx, utxo_set):
                    raise ValueError("invalid chain during UTXO rebuild")
                self.apply_transaction(tx, utxo_set)

        return utxo_set

    def receive_chain_by_work(self, candidate_chain: List[Block]) -> bool:
        if not self.validate_chain(candidate_chain):
            print(f"[{self.name}] reject candidate chain: invalid")
            return False

        current_work = self.total_work()
        candidate_work = self.total_work(candidate_chain)

        print(f"\n[{self.name}] chain work comparison")
        print(f"  current   work: {current_work}")
        print(f"  candidate work: {candidate_work}")

        if candidate_work <= current_work:
            print(f"[{self.name}] keep current chain")
            return False

        old_tip = self.tip_hash()

        self.chain = list(candidate_chain)
        self.utxo_set = self.rebuild_utxo_from_chain(candidate_chain)
        self.remove_invalid_mempool_transactions()

        print(
            f"[{self.name}] REORG by accumulated work "
            f"old_tip={old_tip[:16]}... new_tip={self.tip_hash()[:16]}..."
        )
        return True

    def receive_block_on_tip(self, block: Block) -> bool:
        candidate_chain = self.chain + [block]
        return self.receive_chain_by_work(candidate_chain)

    def remove_invalid_mempool_transactions(self) -> None:
        temp_utxo = self.utxo_set.copy()
        valid_mempool: Dict[str, Transaction] = {}

        for tx_id, tx in self.mempool.items():
            if self.validate_transaction(tx, temp_utxo):
                valid_mempool[tx_id] = tx
                self.apply_transaction(tx, temp_utxo)

        self.mempool = valid_mempool

    def print_chain(self) -> None:
        print(f"\n[{self.name} chain] total_work={self.total_work()}")
        for block in self.chain:
            tx_metas = [tx.meta for tx in block.transactions]
            print(
                f"  height={block.header.height} "
                f"miner={block.header.miner} "
                f"difficulty={block.header.difficulty} "
                f"work={block.work()} "
                f"hash={block.hash()[:16]}... "
                f"txs={tx_metas}"
            )

    def print_balances(self, names: List[str]) -> None:
        print(f"\n[{self.name} balances]")
        for name in names:
            print(f"  {name}: {self.utxo_set.balance_of(name)}")


def main() -> None:
    node_a = Node("NodeA")
    node_b = Node("NodeB")

    weak_miner = Miner("WeakMiner", difficulty=1)
    strong_miner = Miner("StrongMiner", difficulty=5)

    satoshi_wallet = Wallet("Satoshi")

    print("[*] Create shared genesis state")
    node_a.create_genesis_block()
    node_b.clone_from(node_a)

    print("\n[*] Wallet creates two conflicting transactions")
    tx_to_bob = satoshi_wallet.create_transaction(
        visible_utxo_set=node_a.utxo_set,
        recipient="Bob",
        amount=30,
        fee=1,
        meta="Satoshi-to-Bob",
    )

    tx_to_charlie = satoshi_wallet.create_transaction(
        visible_utxo_set=node_a.utxo_set,
        recipient="Charlie",
        amount=30,
        fee=1,
        meta="Satoshi-to-Charlie",
    )

    node_a.submit_transaction(tx_to_bob)
    node_b.submit_transaction(tx_to_charlie)

    print("\n[*] NodeA builds a longer but weaker chain")
    block_a1 = weak_miner.mine_block(node_a)
    node_a.receive_block_on_tip(block_a1)

    block_a2 = weak_miner.mine_block(node_a)
    node_a.receive_block_on_tip(block_a2)

    print("\n[*] NodeB builds a shorter but stronger chain")
    block_b1 = strong_miner.mine_block(node_b)
    node_b.receive_block_on_tip(block_b1)

    node_a.print_chain()
    node_b.print_chain()

    print("\n[*] NodeA receives NodeB's shorter chain")
    print("    NodeB chain has fewer blocks, but more accumulated work.")
    node_a.receive_chain_by_work(node_b.chain)

    node_a.print_chain()
    node_a.print_balances(["Satoshi", "Bob", "Charlie", "WeakMiner", "StrongMiner"])

    print("\n[*] Result")
    print("  NodeA had more blocks.")
    print("  NodeB had more accumulated work.")
    print("  NodeA adopted NodeB's chain.")
    print("  Final surviving tx: Satoshi-to-Charlie")


if __name__ == "__main__":
    main()