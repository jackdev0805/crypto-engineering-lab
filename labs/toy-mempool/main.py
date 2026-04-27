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

    def serialize(self) -> str:
        return self.key()


@dataclass
class TransactionOutput:
    recipient: str
    amount: int

    def serialize(self) -> str:
        return f"{self.recipient}:{self.amount}"


@dataclass
class Transaction:
    inputs: List[TransactionInput]
    outputs: List[TransactionOutput]
    fee: int = 0
    meta: str = ""
    tx_id: str = ""

    def serialize(self) -> str:
        input_part = "|".join(tx_input.serialize() for tx_input in self.inputs)
        output_part = "|".join(tx_output.serialize() for tx_output in self.outputs)
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
    nonce: int = 0

    def serialize(self) -> str:
        return (
            f"{self.index}|"
            f"{self.previous_hash}|"
            f"{self.merkle_root}|"
            f"{self.timestamp}|"
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


class Mempool:
    """
    아직 블록에 포함되지 않은 트랜잭션 대기열.

    핵심 역할:
    - 새 트랜잭션을 임시 보관
    - 동일 UTXO를 쓰는 충돌 트랜잭션 감지
    - 채굴자가 블록에 넣을 후보 트랜잭션 선택
    """

    def __init__(self) -> None:
        self.transactions: Dict[str, Transaction] = {}

    def add(self, tx: Transaction) -> None:
        self.transactions[tx.tx_id] = tx

    def remove(self, tx_id: str) -> None:
        if tx_id in self.transactions:
            del self.transactions[tx_id]

    def all(self) -> List[Transaction]:
        return list(self.transactions.values())

    def clear_confirmed(self, confirmed_txs: List[Transaction]) -> None:
        for tx in confirmed_txs:
            self.remove(tx.tx_id)

    def has_conflicting_input(self, tx: Transaction) -> bool:
        new_inputs = {tx_input.key() for tx_input in tx.inputs}

        for mempool_tx in self.transactions.values():
            existing_inputs = {tx_input.key() for tx_input in mempool_tx.inputs}
            if new_inputs & existing_inputs:
                return True

        return False

    def print(self) -> None:
        print("\n[Mempool]")
        if not self.transactions:
            print("  empty")
            return

        for tx in self.transactions.values():
            input_keys = [tx_input.key() for tx_input in tx.inputs]
            print(f"  tx_id={tx.tx_id[:16]}... fee={tx.fee} inputs={input_keys}")


class Blockchain:
    def __init__(self, difficulty_prefix: int = 4, block_reward: int = 50) -> None:
        self.chain: List[Block] = []
        self.utxo_set = UTXOSet()
        self.mempool = Mempool()
        self.difficulty_prefix = difficulty_prefix
        self.block_reward = block_reward

    def create_genesis_block(self) -> Block:
        coinbase = Transaction.coinbase(
            recipient="Satoshi",
            amount=self.block_reward,
            meta="genesis",
        )

        block = self.create_block(
            transactions=[coinbase],
            previous_hash=ZERO_HASH,
            index=0,
        )

        self.chain.append(block)
        self.apply_block(block)
        return block

    def create_block(
        self,
        transactions: List[Transaction],
        previous_hash: str,
        index: int,
    ) -> Block:
        tx_ids = [tx.tx_id for tx in transactions]
        root = merkle_root(tx_ids)

        header = BlockHeader(
            index=index,
            previous_hash=previous_hash,
            merkle_root=root,
            timestamp=int(time.time()),
        )
        header.mine(self.difficulty_prefix)

        return Block(header=header, transactions=transactions)

    def latest_block(self) -> Block:
        return self.chain[-1]

    def validate_transaction(self, tx: Transaction, utxo_set: UTXOSet) -> bool:
        if not tx.outputs:
            print("[INVALID TX] outputs empty")
            return False

        for output in tx.outputs:
            if output.amount <= 0:
                print("[INVALID TX] output amount must be positive")
                return False

        # coinbase
        if not tx.inputs:
            return True

        seen_inputs = set()
        total_input = 0

        for tx_input in tx.inputs:
            if tx_input.key() in seen_inputs:
                print("[INVALID TX] duplicated input in same tx")
                return False
            seen_inputs.add(tx_input.key())

            utxo = utxo_set.get(tx_input)
            if utxo is None:
                print("[INVALID TX] missing or already spent UTXO")
                return False

            total_input += utxo.amount

        total_output = sum(output.amount for output in tx.outputs)

        if total_input < total_output + tx.fee:
            print("[INVALID TX] outputs + fee exceed inputs")
            return False

        return True

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
        """
        트랜잭션을 mempool에 넣기 전 검증한다.

        여기서는 단순화를 위해:
        - 현재 UTXO 기준으로 유효한지 확인
        - mempool 안의 기존 tx와 같은 input을 쓰는지 확인
        """
        if not tx.tx_id:
            tx.finalize()

        if not self.validate_transaction(tx, self.utxo_set):
            print(f"[REJECTED] invalid tx: {tx.tx_id[:16]}...")
            return False

        if self.mempool.has_conflicting_input(tx):
            print(f"[REJECTED] mempool conflict: {tx.tx_id[:16]}...")
            return False

        self.mempool.add(tx)
        print(f"[ACCEPTED] tx added to mempool: {tx.tx_id[:16]}... fee={tx.fee}")
        return True

    def mine_pending_transactions(self, miner: str, max_txs: int = 2) -> Block:
        """
        mempool에서 수수료가 높은 순서로 트랜잭션을 선택해 블록에 넣는다.
        """
        candidate_txs = sorted(
            self.mempool.all(),
            key=lambda tx: tx.fee,
            reverse=True,
        )

        selected_txs: List[Transaction] = []
        temp_utxo_set = self.utxo_set.copy()

        for tx in candidate_txs:
            if len(selected_txs) >= max_txs:
                break

            if self.validate_transaction(tx, temp_utxo_set):
                selected_txs.append(tx)
                self.apply_transaction(tx, temp_utxo_set)

        total_fees = sum(tx.fee for tx in selected_txs)

        coinbase = Transaction.coinbase(
            recipient=miner,
            amount=self.block_reward + total_fees,
            meta=f"coinbase-height-{len(self.chain)}-fees-{total_fees}",
        )

        block_txs = [coinbase] + selected_txs

        block = self.create_block(
            transactions=block_txs,
            previous_hash=self.latest_block().calculate_hash(),
            index=len(self.chain),
        )

        self.chain.append(block)
        self.apply_block(block)
        self.mempool.clear_confirmed(selected_txs)

        print(
            f"\n[MINED] Block #{block.header.index} "
            f"txs={len(block.transactions)} "
            f"fees={total_fees} "
            f"hash={block.calculate_hash()[:20]}..."
        )

        return block

    def create_transaction(
        self,
        sender: str,
        recipient: str,
        amount: int,
        fee: int,
        meta: str,
    ) -> Transaction:
        """
        학습용 단순 트랜잭션 생성기.
        실제로는 Wallet이 해야 할 일이지만,
        이번 예제에서는 mempool 흐름에 집중하기 위해 간단히 둔다.
        """
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
        print("\n[Balances]")
        for name in names:
            print(f"  {name}: {self.utxo_set.balance_of(name)}")

    def print_chain(self) -> None:
        print("\n[Blockchain]")
        for block in self.chain:
            print("=" * 100)
            print(f"Block #{block.header.index}")
            print(f"  previous_hash : {block.header.previous_hash[:20]}...")
            print(f"  merkle_root   : {block.header.merkle_root}")
            print(f"  nonce         : {block.header.nonce}")
            print(f"  hash          : {block.calculate_hash()}")
            print("  transactions:")
            for tx in block.transactions:
                print(f"    tx={tx.tx_id[:16]}... fee={tx.fee}")
                if not tx.inputs:
                    print("      input : COINBASE")
                else:
                    for tx_input in tx.inputs:
                        print(f"      input : {tx_input.key()}")

                for index, output in enumerate(tx.outputs):
                    print(f"      output[{index}] : {output.recipient} {output.amount}")
        print("=" * 100)


def main() -> None:
    bc = Blockchain(difficulty_prefix=4, block_reward=50)

    print("[*] Creating genesis block")
    bc.create_genesis_block()
    bc.print_balances(["Satoshi", "Alice", "Bob", "Charlie", "Miner1"])

    print("\n[*] Create tx1: Satoshi -> Alice 30, fee 1")
    tx1 = bc.create_transaction(
        sender="Satoshi",
        recipient="Alice",
        amount=30,
        fee=1,
        meta="satoshi-to-alice",
    )
    bc.submit_transaction(tx1)
    bc.mempool.print()

    print("\n[*] Create conflicting tx2: Satoshi -> Bob 30, fee 5")
    print("    This tries to spend the same Satoshi UTXO as tx1.")
    tx2 = bc.create_transaction(
        sender="Satoshi",
        recipient="Bob",
        amount=30,
        fee=5,
        meta="satoshi-to-bob-conflict",
    )
    bc.submit_transaction(tx2)
    bc.mempool.print()

    print("\n[*] Mining pending transactions")
    bc.mine_pending_transactions(miner="Miner1", max_txs=2)
    bc.print_balances(["Satoshi", "Alice", "Bob", "Charlie", "Miner1"])
    bc.mempool.print()

    print("\n[*] Create tx3: Alice -> Charlie 10, fee 2")
    tx3 = bc.create_transaction(
        sender="Alice",
        recipient="Charlie",
        amount=10,
        fee=2,
        meta="alice-to-charlie",
    )
    bc.submit_transaction(tx3)

    print("\n[*] Create tx4: Miner1 -> Bob 20, fee 3")
    tx4 = bc.create_transaction(
        sender="Miner1",
        recipient="Bob",
        amount=20,
        fee=3,
        meta="miner-to-bob",
    )
    bc.submit_transaction(tx4)

    bc.mempool.print()

    print("\n[*] Mining pending transactions by fee priority")
    bc.mine_pending_transactions(miner="Miner1", max_txs=1)
    bc.print_balances(["Satoshi", "Alice", "Bob", "Charlie", "Miner1"])
    bc.mempool.print()

    print("\n[*] Mining remaining pending transactions")
    bc.mine_pending_transactions(miner="Miner1", max_txs=2)
    bc.print_balances(["Satoshi", "Alice", "Bob", "Charlie", "Miner1"])
    bc.mempool.print()

    bc.print_chain()


if __name__ == "__main__":
    main()