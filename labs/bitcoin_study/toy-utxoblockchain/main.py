
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


ZERO_HASH = "0" * 64


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_str(data: str) -> str:
    return sha256_hex(data.encode("utf-8"))


@dataclass
class TransactionInput:
    prev_tx_id: str
    output_index: int

    def serialize(self) -> str:
        return f"{self.prev_tx_id}:{self.output_index}"


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
    meta: str = ""
    tx_id: str = ""

    def calculate_tx_id(self) -> str:
        input_part = "|".join(tx_input.serialize() for tx_input in self.inputs)
        output_part = "|".join(tx_output.serialize() for tx_output in self.outputs)
        raw = f"IN[{input_part}]OUT[{output_part}]META[{self.meta}]"
        return sha256_str(raw)

    def finalize(self) -> None:
        self.tx_id = self.calculate_tx_id()

    @staticmethod
    def coinbase(recipient: str, amount: int, meta: str) -> Transaction:
        tx = Transaction(
            inputs=[],
            outputs=[TransactionOutput(recipient=recipient, amount=amount)],
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


@dataclass
class Block:
    index: int
    timestamp: int
    transactions: List[Transaction]
    previous_hash: str
    nonce: int = 0
    hash: str = ""

    def transactions_summary(self) -> str:
        return "|".join(tx.tx_id for tx in self.transactions)

    def header_without_nonce(self) -> bytes:
        raw = (
            f"{self.index}|{self.timestamp}|"
            f"{self.transactions_summary()}|{self.previous_hash}|"
        )
        return raw.encode("utf-8")

    def calculate_hash_with_nonce(self, nonce: int) -> str:
        return sha256_hex(self.header_without_nonce() + str(nonce).encode("utf-8"))

    def calculate_hash(self) -> str:
        return self.calculate_hash_with_nonce(self.nonce)

    def mine(self, difficulty: int) -> None:
        prefix = "0" * difficulty
        nonce = 0

        while True:
            current_hash = self.calculate_hash_with_nonce(nonce)
            if current_hash.startswith(prefix):
                self.nonce = nonce
                self.hash = current_hash
                return
            nonce += 1


class UTXOSet:
    def __init__(self) -> None:
        self.utxos: Dict[str, UTXO] = {}

    def add_utxo(self, utxo: UTXO) -> None:
        self.utxos[utxo.key()] = utxo

    def remove_utxo(self, prev_tx_id: str, output_index: int) -> None:
        key = f"{prev_tx_id}:{output_index}"
        del self.utxos[key]

    def get_utxo(self, prev_tx_id: str, output_index: int) -> Optional[UTXO]:
        key = f"{prev_tx_id}:{output_index}"
        return self.utxos.get(key)

    def all_for_recipient(self, recipient: str) -> List[UTXO]:
        return [utxo for utxo in self.utxos.values() if utxo.recipient == recipient]

    def balance_of(self, recipient: str) -> int:
        return sum(utxo.amount for utxo in self.all_for_recipient(recipient))

    def snapshot(self) -> Dict[str, UTXO]:
        return dict(self.utxos)


class Blockchain:
    def __init__(self, difficulty: int = 4, block_reward: int = 50) -> None:
        self.difficulty = difficulty
        self.block_reward = block_reward
        self.chain: List[Block] = []
        self.utxo_set = UTXOSet()

        genesis_block = self.create_genesis_block()
        self.chain.append(genesis_block)
        self.apply_block(genesis_block)

    def create_genesis_block(self) -> Block:
        genesis_tx = Transaction.coinbase(
            recipient="Satoshi",
            amount=self.block_reward,
            meta="genesis-block-0"
        )
        block = Block(
            index=0,
            timestamp=int(time.time()),
            transactions=[genesis_tx],
            previous_hash=ZERO_HASH,
        )
        block.mine(self.difficulty)
        return block

    def latest_block(self) -> Block:
        return self.chain[-1]

    def validate_transaction(self, tx: Transaction) -> bool:
        if not tx.outputs:
            print("[INVALID TX] outputs가 비어 있음")
            return False

        if not tx.inputs:
            # coinbase로 간주
            total_output = sum(output.amount for output in tx.outputs)
            if total_output <= 0:
                print("[INVALID TX] coinbase output amount must be positive")
                return False
            return True

        seen_inputs_in_tx = set()
        total_input_amount = 0

        for tx_input in tx.inputs:
            key = (tx_input.prev_tx_id, tx_input.output_index)

            if key in seen_inputs_in_tx:
                print("[INVALID TX] 같은 입력을 한 트랜잭션 안에서 중복 사용")
                return False
            seen_inputs_in_tx.add(key)

            utxo = self.utxo_set.get_utxo(tx_input.prev_tx_id, tx_input.output_index)
            if utxo is None:
                print("[INVALID TX] 존재하지 않거나 이미 소비된 UTXO 사용")
                return False

            total_input_amount += utxo.amount

        total_output_amount = sum(output.amount for output in tx.outputs)

        if total_output_amount <= 0:
            print("[INVALID TX] total output must be positive")
            return False

        for output in tx.outputs:
            if output.amount <= 0:
                print("[INVALID TX] output amount must be positive")
                return False

        if total_input_amount < total_output_amount:
            print("[INVALID TX] 입력 금액보다 출력 금액이 큼")
            return False

        return True

    def apply_transaction(self, tx: Transaction) -> None:
        # 일반 트랜잭션이면 입력 UTXO 소비
        for tx_input in tx.inputs:
            self.utxo_set.remove_utxo(tx_input.prev_tx_id, tx_input.output_index)

        # 새 출력들을 UTXO로 등록
        for index, tx_output in enumerate(tx.outputs):
            utxo = UTXO(
                tx_id=tx.tx_id,
                output_index=index,
                recipient=tx_output.recipient,
                amount=tx_output.amount,
            )
            self.utxo_set.add_utxo(utxo)

    def apply_block(self, block: Block) -> None:
        for tx in block.transactions:
            self.apply_transaction(tx)

    def add_block(self, transactions: List[Transaction], miner: str) -> Block:
        next_index = self.latest_block().index + 1

        coinbase_tx = Transaction.coinbase(
            recipient=miner,
            amount=self.block_reward,
            meta=f"coinbase-height-{next_index}-miner-{miner}-time-{int(time.time())}",
        )

        all_txs = [coinbase_tx] + transactions

        for tx in all_txs:
            if not tx.tx_id:
                tx.finalize()

        # 블록 추가 전에 검증
        for tx in all_txs:
            if not self.validate_transaction(tx):
                raise ValueError(f"invalid transaction: {tx.tx_id}")

        block = Block(
            index=self.latest_block().index + 1,
            timestamp=int(time.time()),
            transactions=all_txs,
            previous_hash=self.latest_block().hash,
        )
        block.mine(self.difficulty)

        # 검증 통과 후 체인에 반영
        self.chain.append(block)
        self.apply_block(block)

        return block

    def create_transaction(self, sender: str, recipient: str, amount: int) -> Transaction:
        if amount <= 0:
            raise ValueError("amount must be positive")

        sender_utxos = self.utxo_set.all_for_recipient(sender)

        selected_utxos: List[UTXO] = []
        total = 0

        for utxo in sender_utxos:
            selected_utxos.append(utxo)
            total += utxo.amount
            if total >= amount:
                break

        if total < amount:
            raise ValueError(f"{sender} balance is insufficient")

        inputs = [
            TransactionInput(prev_tx_id=utxo.tx_id, output_index=utxo.output_index)
            for utxo in selected_utxos
        ]

        outputs = [TransactionOutput(recipient=recipient, amount=amount)]

        change = total - amount
        if change > 0:
            outputs.append(TransactionOutput(recipient=sender, amount=change))

        tx = Transaction(inputs=inputs, outputs=outputs)
        tx.finalize()
        return tx

    def is_valid_chain(self) -> bool:
        prefix = "0" * self.difficulty

        # 체인 검증용 임시 UTXO 집합
        temp_utxo_set = UTXOSet()

        for i, block in enumerate(self.chain):
            if block.hash != block.calculate_hash():
                print(f"[INVALID CHAIN] Block {block.index}: stored hash mismatch")
                return False

            if not block.hash.startswith(prefix):
                print(f"[INVALID CHAIN] Block {block.index}: difficulty mismatch")
                return False

            if i == 0:
                if block.previous_hash != ZERO_HASH:
                    print("[INVALID CHAIN] Genesis previous_hash mismatch")
                    return False
            else:
                if block.previous_hash != self.chain[i - 1].hash:
                    print(f"[INVALID CHAIN] Block {block.index}: previous_hash mismatch")
                    return False

            for tx in block.transactions:
                if not tx.tx_id:
                    print(f"[INVALID CHAIN] Block {block.index}: tx_id missing")
                    return False

                if tx.tx_id != tx.calculate_tx_id():
                    print(f"[INVALID CHAIN] Block {block.index}: tx_id mismatch")
                    return False

                # 검증 시에는 temp_utxo_set을 기준으로 확인
                if not self.validate_transaction_against(tx, temp_utxo_set):
                    print(f"[INVALID CHAIN] Block {block.index}: invalid tx {tx.tx_id}")
                    return False

                self.apply_transaction_against(tx, temp_utxo_set)

        return True

    def validate_transaction_against(self, tx: Transaction, utxo_set: UTXOSet) -> bool:
        if not tx.outputs:
            return False

        if not tx.inputs:
            total_output = sum(output.amount for output in tx.outputs)
            return total_output > 0

        seen_inputs_in_tx = set()
        total_input_amount = 0

        for tx_input in tx.inputs:
            key = (tx_input.prev_tx_id, tx_input.output_index)
            if key in seen_inputs_in_tx:
                return False
            seen_inputs_in_tx.add(key)

            utxo = utxo_set.get_utxo(tx_input.prev_tx_id, tx_input.output_index)
            if utxo is None:
                return False

            total_input_amount += utxo.amount

        total_output_amount = sum(output.amount for output in tx.outputs)

        if total_output_amount <= 0:
            return False

        for output in tx.outputs:
            if output.amount <= 0:
                return False

        return total_input_amount >= total_output_amount

    def apply_transaction_against(self, tx: Transaction, utxo_set: UTXOSet) -> None:
        for tx_input in tx.inputs:
            utxo_set.remove_utxo(tx_input.prev_tx_id, tx_input.output_index)

        for index, tx_output in enumerate(tx.outputs):
            utxo = UTXO(
                tx_id=tx.tx_id,
                output_index=index,
                recipient=tx_output.recipient,
                amount=tx_output.amount,
            )
            utxo_set.add_utxo(utxo)

    def print_chain(self) -> None:
        for block in self.chain:
            print("=" * 100)
            print(f"Block #{block.index}")
            print(f"timestamp     : {block.timestamp}")
            print(f"previous_hash : {block.previous_hash}")
            print(f"nonce         : {block.nonce}")
            print(f"hash          : {block.hash}")
            print("transactions  :")
            for tx in block.transactions:
                print(f"  tx_id: {tx.tx_id}")
                if tx.inputs:
                    for tx_input in tx.inputs:
                        print(f"    input  -> {tx_input.prev_tx_id}:{tx_input.output_index}")
                else:
                    print("    input  -> COINBASE")
                for idx, tx_output in enumerate(tx.outputs):
                    print(f"    output[{idx}] -> {tx_output.recipient}: {tx_output.amount}")
        print("=" * 100)

    def print_balances(self, names: List[str]) -> None:
        print("\n[Balances]")
        for name in names:
            print(f"  {name}: {self.utxo_set.balance_of(name)}")


def main() -> None:
    blockchain = Blockchain(difficulty=4, block_reward=50)

    print("[*] Genesis created")
    blockchain.print_balances(["Satoshi", "Alice", "Bob", "Charlie", "Miner1"])

    # Satoshi -> Alice 30, change 20 back to Satoshi
    print("\n[*] Creating tx1: Satoshi -> Alice (30)")
    tx1 = blockchain.create_transaction("Satoshi", "Alice", 30)

    print("[*] Mining block 1...")
    blockchain.add_block([tx1], miner="Miner1")
    blockchain.print_balances(["Satoshi", "Alice", "Bob", "Charlie", "Miner1"])

    # Alice -> Bob 10, change 20 back to Alice
    print("\n[*] Creating tx2: Alice -> Bob (10)")
    tx2 = blockchain.create_transaction("Alice", "Bob", 10)

    print("[*] Mining block 2...")
    blockchain.add_block([tx2], miner="Miner1")
    blockchain.print_balances(["Satoshi", "Alice", "Bob", "Charlie", "Miner1"])

    # Bob -> Charlie 4, change 6 back to Bob
    print("\n[*] Creating tx3: Bob -> Charlie (4)")
    tx3 = blockchain.create_transaction("Bob", "Charlie", 4)

    print("[*] Mining block 3...")
    blockchain.add_block([tx3], miner="Miner1")
    blockchain.print_balances(["Satoshi", "Alice", "Bob", "Charlie", "Miner1"])

    print("\n[*] Chain dump")
    blockchain.print_chain()

    print(f"\n[*] Chain valid? {blockchain.is_valid_chain()}")

    print("\n[DEBUG] Miner1 UTXOs:")
    for utxo in blockchain.utxo_set.all_for_recipient("Miner1"):
        print(f"{utxo.tx_id}:{utxo.output_index} -> {utxo.amount}")

    print("\n[*] Trying invalid tx: Charlie -> Alice (1000)")
    try:
        bad_tx = blockchain.create_transaction("Charlie", "Alice", 1000)
        blockchain.add_block([bad_tx], miner="Miner1")
    except ValueError as e:
        print(f"[EXPECTED ERROR] {e}")


if __name__ == "__main__":
    main()