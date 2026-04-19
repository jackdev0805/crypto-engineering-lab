from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from ecdsa import BadSignatureError, SECP256k1, SigningKey, VerifyingKey


ZERO_HASH = "0" * 64


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_str(data: str) -> str:
    return sha256_hex(data.encode("utf-8"))


@dataclass
class TransactionInput:
    prev_tx_id: str
    output_index: int
    signature_hex: str = ""
    public_key_hex: str = ""

    def serialize_outpoint(self) -> str:
        return f"{self.prev_tx_id}:{self.output_index}"

    def serialize_full(self) -> str:
        return (
            f"{self.prev_tx_id}:{self.output_index}:"
            f"{self.public_key_hex}:{self.signature_hex}"
        )


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

    def unsigned_payload(self) -> str:
        input_part = "|".join(tx_input.serialize_outpoint() for tx_input in self.inputs)
        output_part = "|".join(tx_output.serialize() for tx_output in self.outputs)
        return f"IN[{input_part}]OUT[{output_part}]META[{self.meta}]"

    def full_payload(self) -> str:
        input_part = "|".join(tx_input.serialize_full() for tx_input in self.inputs)
        output_part = "|".join(tx_output.serialize() for tx_output in self.outputs)
        return f"IN[{input_part}]OUT[{output_part}]META[{self.meta}]"

    def signing_message(self) -> str:
        return sha256_str(self.unsigned_payload())

    def calculate_tx_id(self) -> str:
        return sha256_str(self.full_payload())

    def finalize(self) -> None:
        self.tx_id = self.calculate_tx_id()

    @staticmethod
    def coinbase(recipient: str, amount: int, meta: str) -> "Transaction":
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

    def copy(self) -> "UTXOSet":
        cloned = UTXOSet()
        cloned.utxos = dict(self.utxos)
        return cloned


def sign_message(private_key: SigningKey, message: str) -> str:
    signature = private_key.sign(message.encode("utf-8"))
    return signature.hex()


def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)
        return vk.verify(bytes.fromhex(signature_hex), message.encode("utf-8"))
    except (BadSignatureError, ValueError):
        return False


class Wallet:
    def __init__(self, name: str) -> None:
        self.name = name
        self.private_key = SigningKey.generate(curve=SECP256k1)
        self.public_key = self.private_key.get_verifying_key()

    @property
    def public_key_hex(self) -> str:
        return self.public_key.to_string().hex()

    def balance(self, utxo_set: UTXOSet) -> int:
        return utxo_set.balance_of(self.public_key_hex)

    def create_transaction(
        self,
        utxo_set: UTXOSet,
        recipient_public_key_hex: str,
        amount: int,
        meta: str = "",
    ) -> Transaction:
        if amount <= 0:
            raise ValueError("amount must be positive")

        my_utxos = utxo_set.all_for_recipient(self.public_key_hex)

        selected_utxos: List[UTXO] = []
        total = 0

        for utxo in my_utxos:
            selected_utxos.append(utxo)
            total += utxo.amount
            if total >= amount:
                break

        if total < amount:
            raise ValueError(f"{self.name} balance is insufficient")

        inputs = [
            TransactionInput(prev_tx_id=utxo.tx_id, output_index=utxo.output_index)
            for utxo in selected_utxos
        ]

        outputs = [
            TransactionOutput(recipient=recipient_public_key_hex, amount=amount)
        ]

        change = total - amount
        if change > 0:
            outputs.append(
                TransactionOutput(recipient=self.public_key_hex, amount=change)
            )

        tx = Transaction(
            inputs=inputs,
            outputs=outputs,
            meta=meta or f"from-{self.name}",
        )

        message = tx.signing_message()
        signature_hex = sign_message(self.private_key, message)

        for tx_input in tx.inputs:
            tx_input.public_key_hex = self.public_key_hex
            tx_input.signature_hex = signature_hex

        tx.finalize()
        return tx


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


class Blockchain:
    def __init__(self, difficulty: int = 4, block_reward: int = 50) -> None:
        if difficulty < 1:
            raise ValueError("difficulty must be >= 1")

        self.difficulty = difficulty
        self.block_reward = block_reward
        self.chain: List[Block] = []
        self.utxo_set = UTXOSet()

    def create_genesis_block(self, recipient: str) -> Block:
        genesis_tx = Transaction.coinbase(
            recipient=recipient,
            amount=self.block_reward,
            meta="genesis-block-0",
        )

        block = Block(
            index=0,
            timestamp=int(time.time()),
            transactions=[genesis_tx],
            previous_hash=ZERO_HASH,
        )
        block.mine(self.difficulty)

        self.chain.append(block)
        self.apply_block(block)
        return block

    def latest_block(self) -> Block:
        return self.chain[-1]

    def validate_transaction(self, tx: Transaction, utxo_set: UTXOSet) -> bool:
        if not tx.outputs:
            print("[INVALID TX] outputs가 비어 있음")
            return False

        for output in tx.outputs:
            if output.amount <= 0:
                print("[INVALID TX] output amount must be positive")
                return False

        if not tx.inputs:
            total_output = sum(output.amount for output in tx.outputs)
            if total_output <= 0:
                print("[INVALID TX] invalid coinbase output")
                return False
            return True

        seen_inputs_in_tx = set()
        total_input_amount = 0
        message = tx.signing_message()

        for tx_input in tx.inputs:
            key = (tx_input.prev_tx_id, tx_input.output_index)

            if key in seen_inputs_in_tx:
                print("[INVALID TX] 같은 입력을 한 트랜잭션 안에서 중복 사용")
                return False
            seen_inputs_in_tx.add(key)

            utxo = utxo_set.get_utxo(tx_input.prev_tx_id, tx_input.output_index)
            if utxo is None:
                print("[INVALID TX] 존재하지 않거나 이미 소비된 UTXO 사용")
                return False

            if utxo.recipient != tx_input.public_key_hex:
                print("[INVALID TX] 공개키가 UTXO 소유자와 일치하지 않음")
                return False

            if not tx_input.signature_hex:
                print("[INVALID TX] signature가 비어 있음")
                return False

            if not verify_signature(
                tx_input.public_key_hex,
                message,
                tx_input.signature_hex,
            ):
                print("[INVALID TX] signature 검증 실패")
                return False

            total_input_amount += utxo.amount

        total_output_amount = sum(output.amount for output in tx.outputs)

        if total_input_amount < total_output_amount:
            print("[INVALID TX] 입력 금액보다 출력 금액이 큼")
            return False

        return True

    def apply_transaction(self, tx: Transaction, utxo_set: UTXOSet) -> None:
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

    def apply_block(self, block: Block) -> None:
        for tx in block.transactions:
            self.apply_transaction(tx, self.utxo_set)

    def add_block(self, transactions: List[Transaction], miner_wallet: Wallet) -> Block:
        next_index = self.latest_block().index + 1

        coinbase_tx = Transaction.coinbase(
            recipient=miner_wallet.public_key_hex,
            amount=self.block_reward,
            meta=f"coinbase-height-{next_index}-miner-{miner_wallet.name}",
        )

        all_txs = [coinbase_tx] + transactions

        for tx in all_txs:
            if not tx.tx_id:
                tx.finalize()

        temp_utxo_set = self.utxo_set.copy()

        for tx in all_txs:
            if not self.validate_transaction(tx, temp_utxo_set):
                raise ValueError(f"invalid transaction: {tx.tx_id}")
            self.apply_transaction(tx, temp_utxo_set)

        block = Block(
            index=next_index,
            timestamp=int(time.time()),
            transactions=all_txs,
            previous_hash=self.latest_block().hash,
        )
        block.mine(self.difficulty)

        self.chain.append(block)
        self.apply_block(block)
        return block

    def is_valid_chain(self) -> bool:
        prefix = "0" * self.difficulty
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

                if not self.validate_transaction(tx, temp_utxo_set):
                    print(f"[INVALID CHAIN] Block {block.index}: invalid tx {tx.tx_id}")
                    return False

                self.apply_transaction(tx, temp_utxo_set)

        return True

    def print_balances(self, wallets: List[Wallet]) -> None:
        print("\n[Balances]")
        for wallet in wallets:
            balance = wallet.balance(self.utxo_set)
            utxo_count = len(self.utxo_set.all_for_recipient(wallet.public_key_hex))
            print(f"  {wallet.name}: {balance} ({utxo_count} UTXOs)")

    def print_chain(self, wallet_lookup: Dict[str, str]) -> None:
        def owner_name(pubkey_hex: str) -> str:
            return wallet_lookup.get(pubkey_hex, pubkey_hex[:16] + "...")

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
                        print(
                            f"    input  -> {tx_input.prev_tx_id}:{tx_input.output_index} "
                            f"(pubkey={tx_input.public_key_hex[:16]}..., "
                            f"sig={tx_input.signature_hex[:16]}...)"
                        )
                else:
                    print("    input  -> COINBASE")

                for idx, tx_output in enumerate(tx.outputs):
                    print(
                        f"    output[{idx}] -> "
                        f"{owner_name(tx_output.recipient)}: {tx_output.amount}"
                    )
        print("=" * 100)


def main() -> None:
    satoshi = Wallet("Satoshi")
    alice = Wallet("Alice")
    bob = Wallet("Bob")
    miner1 = Wallet("Miner1")

    wallet_lookup = {
        satoshi.public_key_hex: satoshi.name,
        alice.public_key_hex: alice.name,
        bob.public_key_hex: bob.name,
        miner1.public_key_hex: miner1.name,
    }

    blockchain = Blockchain(difficulty=4, block_reward=50)
    blockchain.create_genesis_block(recipient=satoshi.public_key_hex)

    print("[*] Genesis created")
    blockchain.print_balances([satoshi, alice, bob, miner1])

    print("\n[*] Satoshi creates tx1: send 30 to Alice")
    tx1 = satoshi.create_transaction(
        utxo_set=blockchain.utxo_set,
        recipient_public_key_hex=alice.public_key_hex,
        amount=30,
        meta="satoshi-to-alice",
    )

    print("[*] Mining block 1...")
    blockchain.add_block([tx1], miner1)
    blockchain.print_balances([satoshi, alice, bob, miner1])

    print("\n[*] Alice creates tx2: send 10 to Bob")
    tx2 = alice.create_transaction(
        utxo_set=blockchain.utxo_set,
        recipient_public_key_hex=bob.public_key_hex,
        amount=10,
        meta="alice-to-bob",
    )

    print("[*] Mining block 2...")
    blockchain.add_block([tx2], miner1)
    blockchain.print_balances([satoshi, alice, bob, miner1])

    print("\n[*] Chain dump")
    blockchain.print_chain(wallet_lookup)

    print(f"\n[*] Chain valid? {blockchain.is_valid_chain()}")


if __name__ == "__main__":
    main()