from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


ZERO_HASH = "0" * 64


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
    nonce: int = 0

    def serialize(self) -> str:
        return (
            f"{self.height}|{self.previous_hash}|{self.merkle_root}|"
            f"{self.timestamp}|{self.miner}|{self.nonce}"
        )

    def hash(self) -> str:
        return sha256_str(self.serialize())

    def mine(self, difficulty_prefix: int) -> None:
        prefix = "0" * difficulty_prefix
        nonce = 0

        while True:
            self.nonce = nonce
            if self.hash().startswith(prefix):
                return
            nonce += 1


@dataclass
class Block:
    header: BlockHeader
    transactions: List[Transaction]

    def hash(self) -> str:
        return self.header.hash()


class Wallet:
    """
    Wallet의 역할:
    - 자기 소유 UTXO를 조회한다.
    - 트랜잭션을 만든다.
    - 실제 시스템이라면 private key로 서명한다.
    이 예제는 fork/체인 선택에 집중하기 위해 서명은 생략한다.
    """

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
    """
    Miner의 역할:
    - 특정 Node의 mempool을 보고 거래를 고른다.
    - coinbase transaction을 만든다.
    - block header를 만들고 PoW를 수행한다.
    """

    def __init__(self, name: str) -> None:
        self.name = name

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
        )

        header.mine(node.difficulty_prefix)

        return Block(header=header, transactions=block_txs)


class Node:
    """
    Node의 역할:
    - 블록체인 상태를 보관한다.
    - UTXOSet을 관리한다.
    - 트랜잭션을 검증하고 mempool에 보관한다.
    - 블록을 검증하고 수신한다.
    - 더 긴 체인을 받으면 reorg한다.
    """

    def __init__(self, name: str, difficulty_prefix: int = 4, block_reward: int = 50):
        self.name = name
        self.difficulty_prefix = difficulty_prefix
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
        )
        header.mine(self.difficulty_prefix)

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

    def validate_block_on_tip(self, block: Block) -> bool:
        if block.header.previous_hash != self.tip_hash():
            return False

        if not block.hash().startswith("0" * self.difficulty_prefix):
            return False

        recalculated_root = merkle_root([tx.tx_id for tx in block.transactions])
        if recalculated_root != block.header.merkle_root:
            return False

        temp_utxo = self.utxo_set.copy()

        for tx in block.transactions:
            if not self.validate_transaction(tx, temp_utxo):
                return False
            self.apply_transaction(tx, temp_utxo)

        return True

    def receive_block(self, block: Block) -> bool:
        if not self.validate_block_on_tip(block):
            print(f"[{self.name}] reject block #{block.header.height}")
            return False

        self.chain.append(block)
        self.apply_block(block)
        self.cleanup_mempool_after_new_block(block)

        print(
            f"[{self.name}] accept block #{block.header.height} "
            f"hash={block.hash()[:20]}..."
        )
        return True

    def cleanup_mempool_after_new_block(self, block: Block) -> None:
        confirmed_tx_ids = {tx.tx_id for tx in block.transactions}
        spent_inputs = {
            tx_input.key()
            for tx in block.transactions
            for tx_input in tx.inputs
        }

        remove_ids = []

        for tx_id, mem_tx in self.mempool.items():
            mem_inputs = {tx_input.key() for tx_input in mem_tx.inputs}

            if tx_id in confirmed_tx_ids or mem_inputs & spent_inputs:
                remove_ids.append(tx_id)

        for tx_id in remove_ids:
            self.mempool.pop(tx_id, None)

    def rebuild_utxo_from_chain(self, chain: List[Block]) -> UTXOSet:
        utxo_set = UTXOSet()

        for block in chain:
            for tx in block.transactions:
                if not self.validate_transaction(tx, utxo_set):
                    raise ValueError("invalid chain during UTXO rebuild")
                self.apply_transaction(tx, utxo_set)

        return utxo_set

    def receive_longer_chain(self, candidate_chain: List[Block]) -> bool:
        """
        학습용 reorg:
        - candidate_chain이 현재 chain보다 길면 채택한다.
        - 실제 비트코인은 단순 길이가 아니라 accumulated work 기준이다.
        """
        if len(candidate_chain) <= len(self.chain):
            print(f"[{self.name}] keep current chain; candidate is not longer")
            return False

        rebuilt_utxo = self.rebuild_utxo_from_chain(candidate_chain)

        old_tip = self.tip_hash()
        self.chain = list(candidate_chain)
        self.utxo_set = rebuilt_utxo

        self.remove_invalid_mempool_transactions()

        print(
            f"[{self.name}] REORG: adopted longer chain "
            f"old_tip={old_tip[:16]}... new_tip={self.tip_hash()[:16]}..."
        )
        return True

    def remove_invalid_mempool_transactions(self) -> None:
        temp_utxo = self.utxo_set.copy()
        valid_mempool: Dict[str, Transaction] = {}

        for tx_id, tx in self.mempool.items():
            if self.validate_transaction(tx, temp_utxo):
                valid_mempool[tx_id] = tx
                self.apply_transaction(tx, temp_utxo)

        self.mempool = valid_mempool

    def print_balances(self, names: List[str]) -> None:
        print(f"\n[{self.name} balances]")
        for name in names:
            print(f"  {name}: {self.utxo_set.balance_of(name)}")

    def print_chain(self) -> None:
        print(f"\n[{self.name} chain]")
        for block in self.chain:
            tx_metas = [tx.meta for tx in block.transactions]
            print(
                f"  height={block.header.height} "
                f"miner={block.header.miner} "
                f"hash={block.hash()[:16]}... "
                f"txs={tx_metas}"
            )

    def print_mempool(self) -> None:
        print(f"\n[{self.name} mempool]")
        if not self.mempool:
            print("  empty")
            return

        for tx in self.mempool.values():
            print(f"  {tx.meta} fee={tx.fee} tx_id={tx.tx_id[:16]}...")


def main() -> None:
    node_a = Node("NodeA")
    node_b = Node("NodeB")

    miner_a = Miner("MinerA")
    miner_b = Miner("MinerB")

    satoshi_wallet = Wallet("Satoshi")

    print("[*] Create shared genesis state")
    node_a.create_genesis_block()
    node_b.clone_from(node_a)

    node_a.print_balances(["Satoshi", "Bob", "Charlie", "MinerA", "MinerB"])

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
        fee=5,
        meta="Satoshi-to-Charlie",
    )

    print("\n[*] Network delay: different nodes receive different tx first")
    node_a.submit_transaction(tx_to_bob)
    node_b.submit_transaction(tx_to_charlie)

    node_a.print_mempool()
    node_b.print_mempool()

    print("\n[*] Competing miners produce competing blocks at same height")
    block_a1 = miner_a.mine_block(node_a)
    block_b1 = miner_b.mine_block(node_b)

    print("\n[*] Each node accepts its own mined block")
    node_a.receive_block(block_a1)
    node_b.receive_block(block_b1)

    node_a.print_chain()
    node_b.print_chain()

    print("\n[*] NodeA receives NodeB's block, but it does not extend NodeA's tip")
    node_a.receive_block(block_b1)

    print("\n[*] MinerB finds one more block on top of NodeB's chain")
    block_b2 = miner_b.mine_block(node_b)
    node_b.receive_block(block_b2)

    node_b.print_chain()

    print("\n[*] NodeA receives NodeB's longer chain and reorganizes")
    node_a.receive_longer_chain(node_b.chain)

    node_a.print_chain()
    node_a.print_balances(["Satoshi", "Bob", "Charlie", "MinerA", "MinerB"])
    node_a.print_mempool()

    print("\n[*] Result")
    print("  NodeA first confirmed Satoshi-to-Bob.")
    print("  NodeB confirmed Satoshi-to-Charlie on a competing fork.")
    print("  NodeB's fork became longer.")
    print("  NodeA reorganized to NodeB's chain.")
    print("  Final result: Satoshi-to-Charilie survives; Satoshi-to-Bob is rolled back.")


if __name__ == "__main__":
    main()