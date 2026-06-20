from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


ZERO_HASH = "0" * 64


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_str(data: str) -> str:
    return sha256_hex(data.encode("utf-8"))


def merkle_root(tx_ids: List[str]) -> str:
    if not tx_ids:
        return ""

    current = tx_ids[:]

    while len(current) > 1:
        next_level = []

        for i in range(0, len(current), 2):
            left = current[i]
            right = current[i + 1] if i + 1 < len(current) else left
            next_level.append(sha256_str(left + right))

        current = next_level

    return current[0]


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
    fee: int = 0
    meta: str = ""
    tx_id: str = ""

    def serialize(self) -> str:
        input_part = "|".join(tx_input.key() for tx_input in self.inputs)
        output_part = "|".join(f"{out.recipient}:{out.amount}" for out in self.outputs)
        return f"IN[{input_part}]OUT[{output_part}]FEE[{self.fee}]META[{self.meta}]"

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

    def remove(self, tx_input: TransactionInput) -> None:
        del self.utxos[tx_input.key()]

    def get(self, tx_input: TransactionInput) -> Optional[UTXO]:
        return self.utxos.get(tx_input.key())

    def all_for_recipient(self, recipient: str) -> List[UTXO]:
        return [utxo for utxo in self.utxos.values() if utxo.recipient == recipient]

    def balance_of(self, recipient: str) -> int:
        return sum(utxo.amount for utxo in self.all_for_recipient(recipient))


@dataclass
class BlockHeader:
    index: int
    previous_hash: str
    merkle_root: str
    timestamp: int
    miner: str
    nonce: int = 0

    def serialize(self) -> str:
        return (
            f"{self.index}|"
            f"{self.previous_hash}|"
            f"{self.merkle_root}|"
            f"{self.timestamp}|"
            f"{self.miner}|"
            f"{self.nonce}"
        )

    def calculate_hash(self) -> str:
        return sha256_str(self.serialize())

    def mine(self, difficulty_prefix: int) -> None:
        prefix = "0" * difficulty_prefix
        nonce = 0

        while True:
            self.nonce = nonce
            if self.calculate_hash().startswith(prefix):
                return
            nonce += 1


@dataclass
class Block:
    header: BlockHeader
    transactions: List[Transaction]

    def calculate_hash(self) -> str:
        return self.header.calculate_hash()


class ChainState:
    """
    각 노드가 가지고 있는 체인 상태.
    실제 네트워크에서는 노드마다 체인과 mempool이 일시적으로 다를 수 있다.
    """

    def __init__(self, node_name: str, difficulty_prefix: int = 4, block_reward: int = 50):
        self.node_name = node_name
        self.difficulty_prefix = difficulty_prefix
        self.block_reward = block_reward
        self.chain: List[Block] = []
        self.utxo_set = UTXOSet()
        self.mempool: Dict[str, Transaction] = {}

    def clone_from(self, other: "ChainState") -> None:
        self.chain = list(other.chain)
        self.utxo_set = other.utxo_set.copy()
        self.mempool = dict(other.mempool)

    def latest_block(self) -> Block:
        return self.chain[-1]

    def validate_transaction(self, tx: Transaction, utxo_set: UTXOSet) -> bool:
        if not tx.outputs:
            return False

        for output in tx.outputs:
            if output.amount <= 0:
                return False

        if not tx.inputs:
            return True

        seen_inputs = set()
        total_input = 0

        for tx_input in tx.inputs:
            if tx_input.key() in seen_inputs:
                return False
            seen_inputs.add(tx_input.key())

            utxo = utxo_set.get(tx_input)
            if utxo is None:
                return False

            total_input += utxo.amount

        total_output = sum(output.amount for output in tx.outputs)

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

    def create_block(self, transactions: List[Transaction], miner: str) -> Block:
        tx_ids = [tx.tx_id for tx in transactions]
        root = merkle_root(tx_ids)

        header = BlockHeader(
            index=len(self.chain),
            previous_hash=self.latest_block().calculate_hash() if self.chain else ZERO_HASH,
            merkle_root=root,
            timestamp=int(time.time()),
            miner=miner,
        )
        header.mine(self.difficulty_prefix)

        return Block(header=header, transactions=transactions)

    def create_genesis_block(self) -> None:
        coinbase = Transaction.coinbase(
            recipient="Satoshi",
            amount=self.block_reward,
            meta="genesis",
        )

        block = self.create_block([coinbase], miner="genesis")
        self.chain.append(block)
        self.apply_block(block)

    def submit_transaction(self, tx: Transaction) -> bool:
        if not tx.tx_id:
            tx.finalize()

        if not self.validate_transaction(tx, self.utxo_set):
            print(f"[{self.node_name}] rejected invalid tx {tx.tx_id[:16]}...")
            return False

        # 노드의 mempool 안에서는 같은 input을 쓰는 tx를 동시에 받지 않도록 처리
        new_inputs = {tx_input.key() for tx_input in tx.inputs}

        for existing_tx in self.mempool.values():
            existing_inputs = {tx_input.key() for tx_input in existing_tx.inputs}
            if new_inputs & existing_inputs:
                print(f"[{self.node_name}] rejected mempool conflict {tx.tx_id[:16]}...")
                return False

        self.mempool[tx.tx_id] = tx
        print(f"[{self.node_name}] accepted tx {tx.tx_id[:16]}... meta={tx.meta}")
        return True

    def mine_one_block_from_mempool(self, miner: str) -> Block:
        candidate_txs = sorted(
            self.mempool.values(),
            key=lambda tx: tx.fee,
            reverse=True,
        )

        selected: List[Transaction] = []
        temp_utxo = self.utxo_set.copy()

        for tx in candidate_txs:
            if self.validate_transaction(tx, temp_utxo):
                selected.append(tx)
                self.apply_transaction(tx, temp_utxo)

        total_fees = sum(tx.fee for tx in selected)

        coinbase = Transaction.coinbase(
            recipient=miner,
            amount=self.block_reward + total_fees,
            meta=f"coinbase-{self.node_name}-height-{len(self.chain)}",
        )

        block = self.create_block([coinbase] + selected, miner=miner)
        self.chain.append(block)
        self.apply_block(block)

        for tx in selected:
            self.mempool.pop(tx.tx_id, None)

        print(
            f"[{self.node_name}] mined block #{block.header.index} "
            f"hash={block.calculate_hash()[:20]}... txs={len(block.transactions)}"
        )

        return block

    def receive_block(self, block: Block) -> bool:
        """
        다른 노드가 채굴한 블록을 수신하는 상황.
        단순화를 위해 이 예제에서는 현재 tip 다음 블록만 받는다.
        """
        expected_previous = self.latest_block().calculate_hash()

        if block.header.previous_hash != expected_previous:
            print(f"[{self.node_name}] rejected block: previous hash mismatch")
            return False

        temp_utxo = self.utxo_set.copy()

        for tx in block.transactions:
            if not self.validate_transaction(tx, temp_utxo):
                print(f"[{self.node_name}] rejected block: invalid tx {tx.tx_id[:16]}...")
                return False
            self.apply_transaction(tx, temp_utxo)

        self.chain.append(block)
        self.utxo_set = temp_utxo

        # 블록에 포함된 tx와 충돌하는 mempool tx 제거
        confirmed_inputs = {
            tx_input.key()
            for tx in block.transactions
            for tx_input in tx.inputs
        }

        to_remove = []
        for tx_id, mem_tx in self.mempool.items():
            mem_inputs = {tx_input.key() for tx_input in mem_tx.inputs}
            if tx_id in [tx.tx_id for tx in block.transactions] or mem_inputs & confirmed_inputs:
                to_remove.append(tx_id)

        for tx_id in to_remove:
            self.mempool.pop(tx_id, None)

        print(f"[{self.node_name}] accepted block #{block.header.index}")
        return True

    def create_transaction(self, sender: str, recipient: str, amount: int, fee: int, meta: str) -> Transaction:
        sender_utxos = self.utxo_set.all_for_recipient(sender)

        selected: List[UTXO] = []
        total = 0

        for utxo in sender_utxos:
            selected.append(utxo)
            total += utxo.amount
            if total >= amount + fee:
                break

        if total < amount + fee:
            raise ValueError(f"{sender} has insufficient balance")

        inputs = [
            TransactionInput(prev_tx_id=utxo.tx_id, output_index=utxo.output_index)
            for utxo in selected
        ]

        outputs = [TransactionOutput(recipient=recipient, amount=amount)]

        change = total - amount - fee
        if change > 0:
            outputs.append(TransactionOutput(recipient=sender, amount=change))

        tx = Transaction(inputs=inputs, outputs=outputs, fee=fee, meta=meta)
        tx.finalize()
        return tx

    def print_balances(self, names: List[str]) -> None:
        print(f"\n[{self.node_name} Balances]")
        for name in names:
            print(f"  {name}: {self.utxo_set.balance_of(name)}")

    def print_mempool(self) -> None:
        print(f"\n[{self.node_name} Mempool]")
        if not self.mempool:
            print("  empty")
            return

        for tx in self.mempool.values():
            inputs = [tx_input.key() for tx_input in tx.inputs]
            print(f"  {tx.tx_id[:16]}... meta={tx.meta} fee={tx.fee} inputs={inputs}")


def main() -> None:
    node_a = ChainState("NodeA")
    node_b = ChainState("NodeB")

    print("[*] Create shared genesis state")
    node_a.create_genesis_block()
    node_b.clone_from(node_a)

    node_a.print_balances(["Satoshi", "Bob", "Charlie", "MinerA", "MinerB"])

    print("\n[*] Satoshi creates two conflicting transactions from the same UTXO")
    tx_to_bob = node_a.create_transaction(
        sender="Satoshi",
        recipient="Bob",
        amount=30,
        fee=1,
        meta="Satoshi-to-Bob",
    )

    tx_to_charlie = node_a.create_transaction(
        sender="Satoshi",
        recipient="Charlie",
        amount=30,
        fee=5,
        meta="Satoshi-to-Charlie-conflict",
    )

    print("\n[*] Due to network delay, different nodes receive different transactions first")
    node_a.submit_transaction(tx_to_bob)
    node_b.submit_transaction(tx_to_charlie)

    node_a.print_mempool()
    node_b.print_mempool()

    print("\n[*] NodeA mines a block including tx_to_bob")
    block_from_a = node_a.mine_one_block_from_mempool(miner="MinerA")

    print("\n[*] NodeB receives NodeA's block")
    node_b.receive_block(block_from_a)

    node_a.print_balances(["Satoshi", "Bob", "Charlie", "MinerA", "MinerB"])
    node_b.print_balances(["Satoshi", "Bob", "Charlie", "MinerA", "MinerB"])

    node_a.print_mempool()
    node_b.print_mempool()

    print("\n[*] Result")
    print("  tx_to_bob was confirmed.")
    print("  tx_to_charlie became invalid because it tried to spend the same UTXO.")


if __name__ == "__main__":
    main()