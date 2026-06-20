from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from ecdsa import BadSignatureError, SECP256k1, SigningKey, VerifyingKey


ZERO_HASH = "0" * 64
MAX_TARGET = int("f" * 64, 16)


def sha256_str(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def public_key_to_address(public_key_hex: str) -> str:
    return "addr_" + sha256_str(public_key_hex)[:40]


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


def sign_message(private_key: SigningKey, message: str) -> str:
    return private_key.sign(message.encode("utf-8")).hex()


def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)
        return vk.verify(bytes.fromhex(signature_hex), message.encode("utf-8"))
    except (BadSignatureError, ValueError):
        return False


@dataclass
class TransactionInput:
    prev_tx_id: str
    output_index: int
    public_key_hex: str = ""
    signature_hex: str = ""

    def key(self) -> str:
        return f"{self.prev_tx_id}:{self.output_index}"

    def serialize_unsigned(self) -> str:
        return self.key()

    def serialize_full(self) -> str:
        return f"{self.key()}:{self.public_key_hex}:{self.signature_hex}"


@dataclass
class TransactionOutput:
    recipient_address: str
    amount: int

    def serialize(self) -> str:
        return f"{self.recipient_address}:{self.amount}"


@dataclass
class Transaction:
    inputs: List[TransactionInput]
    outputs: List[TransactionOutput]
    fee: int
    meta: str
    tx_id: str = ""

    def unsigned_payload(self) -> str:
        ins = "|".join(tx_input.serialize_unsigned() for tx_input in self.inputs)
        outs = "|".join(output.serialize() for output in self.outputs)
        return f"IN[{ins}]OUT[{outs}]FEE[{self.fee}]META[{self.meta}]"

    def signing_message(self) -> str:
        return sha256_str(self.unsigned_payload())

    def full_payload(self) -> str:
        ins = "|".join(tx_input.serialize_full() for tx_input in self.inputs)
        outs = "|".join(output.serialize() for output in self.outputs)
        return f"IN[{ins}]OUT[{outs}]FEE[{self.fee}]META[{self.meta}]"

    def finalize(self) -> None:
        self.tx_id = sha256_str(self.full_payload())

    @staticmethod
    def coinbase(recipient_address: str, amount: int, meta: str) -> "Transaction":
        tx = Transaction(
            inputs=[],
            outputs=[TransactionOutput(recipient_address=recipient_address, amount=amount)],
            fee=0,
            meta=meta,
        )
        tx.finalize()
        return tx


@dataclass
class UTXO:
    tx_id: str
    output_index: int
    recipient_address: str
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

    def all_for_address(self, address: str) -> List[UTXO]:
        return [utxo for utxo in self.utxos.values() if utxo.recipient_address == address]

    def balance_of(self, address: str) -> int:
        return sum(utxo.amount for utxo in self.all_for_address(address))


class Wallet:
    def __init__(self, name: str) -> None:
        self.name = name
        self.private_key = SigningKey.generate(curve=SECP256k1)
        self.public_key = self.private_key.get_verifying_key()

    @property
    def public_key_hex(self) -> str:
        return self.public_key.to_string().hex()

    @property
    def address(self) -> str:
        return public_key_to_address(self.public_key_hex)

    def balance(self, utxo_set: UTXOSet) -> int:
        return utxo_set.balance_of(self.address)

    def create_transaction(
        self,
        visible_utxo_set: UTXOSet,
        recipient_address: str,
        amount: int,
        fee: int,
        meta: str,
    ) -> Transaction:
        if amount <= 0:
            raise ValueError("amount must be positive")
        if fee < 0:
            raise ValueError("fee must be >= 0")

        available_utxos = visible_utxo_set.all_for_address(self.address)

        selected: List[UTXO] = []
        total_input = 0

        for utxo in available_utxos:
            selected.append(utxo)
            total_input += utxo.amount
            if total_input >= amount + fee:
                break

        if total_input < amount + fee:
            raise ValueError(f"{self.name} has insufficient balance")

        inputs = [
            TransactionInput(prev_tx_id=utxo.tx_id, output_index=utxo.output_index)
            for utxo in selected
        ]

        outputs = [TransactionOutput(recipient_address=recipient_address, amount=amount)]

        change = total_input - amount - fee
        if change > 0:
            outputs.append(TransactionOutput(recipient_address=self.address, amount=change))

        tx = Transaction(inputs=inputs, outputs=outputs, fee=fee, meta=meta)

        message = tx.signing_message()
        signature_hex = sign_message(self.private_key, message)

        for tx_input in tx.inputs:
            tx_input.public_key_hex = self.public_key_hex
            tx_input.signature_hex = signature_hex

        tx.finalize()
        return tx


@dataclass
class BlockHeader:
    height: int
    previous_hash: str
    merkle_root: str
    timestamp: int
    difficulty: int
    miner_address: str
    nonce: int = 0

    def serialize(self) -> str:
        return (
            f"{self.height}|{self.previous_hash}|{self.merkle_root}|"
            f"{self.timestamp}|{self.difficulty}|{self.miner_address}|{self.nonce}"
        )

    def hash(self) -> str:
        return sha256_str(self.serialize())

    def hash_as_int(self) -> int:
        return int(self.hash(), 16)

    def target(self) -> int:
        return difficulty_to_target(self.difficulty)

    def work(self) -> int:
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


class Mempool:
    def __init__(self) -> None:
        self.transactions: Dict[str, Transaction] = {}

    def all(self) -> List[Transaction]:
        return list(self.transactions.values())

    def add(self, tx: Transaction) -> None:
        self.transactions[tx.tx_id] = tx

    def remove(self, tx_id: str) -> None:
        self.transactions.pop(tx_id, None)

    def has_input_conflict(self, tx: Transaction) -> bool:
        new_inputs = {tx_input.key() for tx_input in tx.inputs}

        for existing_tx in self.transactions.values():
            existing_inputs = {tx_input.key() for tx_input in existing_tx.inputs}
            if new_inputs & existing_inputs:
                return True

        return False

    def remove_confirmed_or_conflicting(self, block: Block) -> None:
        confirmed_tx_ids = {tx.tx_id for tx in block.transactions}
        spent_inputs = {
            tx_input.key()
            for tx in block.transactions
            for tx_input in tx.inputs
        }

        to_remove: List[str] = []

        for tx_id, mem_tx in self.transactions.items():
            mem_inputs = {tx_input.key() for tx_input in mem_tx.inputs}

            if tx_id in confirmed_tx_ids or mem_inputs & spent_inputs:
                to_remove.append(tx_id)

        for tx_id in to_remove:
            self.remove(tx_id)

    def print(self) -> None:
        print("\n[Mempool]")
        if not self.transactions:
            print("  empty")
            return

        for tx in self.transactions.values():
            input_keys = [tx_input.key() for tx_input in tx.inputs]
            print(f"  {tx.meta} | fee={tx.fee} | tx_id={tx.tx_id[:16]}... | inputs={input_keys}")


class Node:
    def __init__(self, name: str, block_reward: int = 50, difficulty: int = 1000) -> None:
        self.name = name
        self.block_reward = block_reward
        self.difficulty = difficulty

        self.chain: List[Block] = []
        self.utxo_set = UTXOSet()
        self.mempool = Mempool()

    def height(self) -> int:
        return len(self.chain)

    def tip_hash(self) -> str:
        if not self.chain:
            return ZERO_HASH
        return self.chain[-1].hash()

    def total_work(self, chain: Optional[List[Block]] = None) -> int:
        selected_chain = chain if chain is not None else self.chain
        return sum(block.work() for block in selected_chain)

    def create_genesis_block(self, recipient_address: str) -> None:
        coinbase = Transaction.coinbase(
            recipient_address=recipient_address,
            amount=self.block_reward,
            meta="genesis-coinbase",
        )

        root = merkle_root([coinbase.tx_id])

        header = BlockHeader(
            height=0,
            previous_hash=ZERO_HASH,
            merkle_root=root,
            timestamp=int(time.time()),
            difficulty=self.difficulty,
            miner_address=recipient_address,
        )
        header.mine()

        block = Block(header=header, transactions=[coinbase])

        self.chain.append(block)
        self.apply_block(block)

    def validate_transaction(self, tx: Transaction, utxo_set: UTXOSet) -> bool:
        if not tx.tx_id:
            print("[INVALID TX] missing tx_id")
            return False

        if tx.tx_id != sha256_str(tx.full_payload()):
            print("[INVALID TX] tx_id mismatch")
            return False

        if not tx.outputs:
            print("[INVALID TX] outputs empty")
            return False

        for output in tx.outputs:
            if output.amount <= 0:
                print("[INVALID TX] output amount must be positive")
                return False

        # coinbase
        if not tx.inputs:
            total_output = sum(output.amount for output in tx.outputs)
            return total_output > 0

        seen_inputs = set()
        total_input = 0
        message = tx.signing_message()

        for tx_input in tx.inputs:
            if tx_input.key() in seen_inputs:
                print("[INVALID TX] duplicate input in same tx")
                return False
            seen_inputs.add(tx_input.key())

            utxo = utxo_set.get(tx_input)
            if utxo is None:
                print("[INVALID TX] missing or already spent UTXO")
                return False

            if not tx_input.public_key_hex:
                print("[INVALID TX] missing public key")
                return False

            derived_address = public_key_to_address(tx_input.public_key_hex)
            if derived_address != utxo.recipient_address:
                print("[INVALID TX] public key does not match UTXO owner address")
                return False

            if not tx_input.signature_hex:
                print("[INVALID TX] missing signature")
                return False

            if not verify_signature(
                public_key_hex=tx_input.public_key_hex,
                message=message,
                signature_hex=tx_input.signature_hex,
            ):
                print("[INVALID TX] bad signature")
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
                    recipient_address=output.recipient_address,
                    amount=output.amount,
                )
            )

    def apply_block(self, block: Block) -> None:
        for tx in block.transactions:
            self.apply_transaction(tx, self.utxo_set)

    def submit_transaction(self, tx: Transaction) -> bool:
        if not self.validate_transaction(tx, self.utxo_set):
            print(f"[{self.name}] reject invalid tx: {tx.meta}")
            return False

        if self.mempool.has_input_conflict(tx):
            print(f"[{self.name}] reject mempool conflict: {tx.meta}")
            return False

        self.mempool.add(tx)
        print(f"[{self.name}] accept tx into mempool: {tx.meta}")
        return True

    def validate_block_on_tip(self, block: Block) -> bool:
        if block.header.previous_hash != self.tip_hash():
            print(f"[{self.name}] invalid block: previous hash mismatch")
            return False

        if not block.header.is_valid_pow():
            print(f"[{self.name}] invalid block: bad proof of work")
            return False

        recalculated_root = merkle_root([tx.tx_id for tx in block.transactions])
        if block.header.merkle_root != recalculated_root:
            print(f"[{self.name}] invalid block: merkle root mismatch")
            return False

        temp_utxo = self.utxo_set.copy()
        total_fees = 0

        for index, tx in enumerate(block.transactions):
            if not self.validate_transaction(tx, temp_utxo):
                print(f"[{self.name}] invalid block: bad tx {tx.meta}")
                return False

            if index > 0:
                total_fees += tx.fee

            self.apply_transaction(tx, temp_utxo)

        coinbase = block.transactions[0]
        coinbase_output_sum = sum(output.amount for output in coinbase.outputs)

        if coinbase.inputs:
            print(f"[{self.name}] invalid block: first tx is not coinbase")
            return False

        if coinbase_output_sum > self.block_reward + total_fees:
            print(f"[{self.name}] invalid block: coinbase reward too high")
            return False

        return True

    def receive_block_on_tip(self, block: Block) -> bool:
        if not self.validate_block_on_tip(block):
            print(f"[{self.name}] reject block height={block.header.height}")
            return False

        self.chain.append(block)
        self.apply_block(block)
        self.mempool.remove_confirmed_or_conflicting(block)

        print(
            f"[{self.name}] accept block height={block.header.height} "
            f"hash={block.hash()[:16]}..."
        )
        return True

    def print_balances(self, wallets: List[Wallet]) -> None:
        print(f"\n[{self.name} Balances]")
        for wallet in wallets:
            print(f"  {wallet.name}: {wallet.balance(self.utxo_set)}")

    def print_chain(self) -> None:
        print(f"\n[{self.name} Chain] height={self.height()} total_work={self.total_work()}")
        for block in self.chain:
            tx_metas = [tx.meta for tx in block.transactions]
            print(
                f"  height={block.header.height} "
                f"hash={block.hash()[:16]}... "
                f"work={block.work()} "
                f"txs={tx_metas}"
            )


class Miner:
    def __init__(self, wallet: Wallet) -> None:
        self.wallet = wallet

    def mine_from_node(self, node: Node, max_txs: int = 10) -> Block:
        selected: List[Transaction] = []
        temp_utxo = node.utxo_set.copy()

        candidates = sorted(
            node.mempool.all(),
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
            recipient_address=self.wallet.address,
            amount=node.block_reward + total_fees,
            meta=f"coinbase-height-{node.height()}-miner-{self.wallet.name}",
        )

        block_txs = [coinbase] + selected
        root = merkle_root([tx.tx_id for tx in block_txs])

        header = BlockHeader(
            height=node.height(),
            previous_hash=node.tip_hash(),
            merkle_root=root,
            timestamp=int(time.time()),
            difficulty=node.difficulty,
            miner_address=self.wallet.address,
        )
        header.mine()

        return Block(header=header, transactions=block_txs)


def main() -> None:
    satoshi = Wallet("Satoshi")
    alice = Wallet("Alice")
    bob = Wallet("Bob")
    miner_wallet = Wallet("Miner1")

    node = Node("Node1", block_reward=50, difficulty=1000)
    miner = Miner(miner_wallet)

    print("[*] Create genesis block")
    node.create_genesis_block(recipient_address=satoshi.address)
    node.print_balances([satoshi, alice, bob, miner_wallet])

    print("\n[*] Satoshi creates transaction to Alice")
    tx1 = satoshi.create_transaction(
        visible_utxo_set=node.utxo_set,
        recipient_address=alice.address,
        amount=30,
        fee=1,
        meta="Satoshi-to-Alice",
    )
    node.submit_transaction(tx1)
    node.mempool.print()

    print("\n[*] Miner mines pending transaction")
    block1 = miner.mine_from_node(node)
    node.receive_block_on_tip(block1)
    node.print_balances([satoshi, alice, bob, miner_wallet])
    node.mempool.print()

    print("\n[*] Alice creates transaction to Bob")
    tx2 = alice.create_transaction(
        visible_utxo_set=node.utxo_set,
        recipient_address=bob.address,
        amount=10,
        fee=2,
        meta="Alice-to-Bob",
    )
    node.submit_transaction(tx2)

    print("\n[*] Tampered transaction attempt")
    tampered_tx = alice.create_transaction(
        visible_utxo_set=node.utxo_set,
        recipient_address=bob.address,
        amount=3,
        fee=1,
        meta="Alice-to-Bob-tampered",
    )
    tampered_tx.outputs[0].amount = 999
    tampered_tx.finalize()
    node.submit_transaction(tampered_tx)

    print("\n[*] Miner mines valid pending transactions")
    block2 = miner.mine_from_node(node)
    node.receive_block_on_tip(block2)

    node.print_balances([satoshi, alice, bob, miner_wallet])
    node.mempool.print()
    node.print_chain()


if __name__ == "__main__":
    main()