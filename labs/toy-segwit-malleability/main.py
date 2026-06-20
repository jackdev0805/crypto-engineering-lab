from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List

from ecdsa import BadSignatureError, SECP256k1, SigningKey, VerifyingKey


def sha256_str(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def sign_message(private_key: SigningKey, message: str) -> str:
    return private_key.sign(message.encode("utf-8")).hex()


def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    try:
        verifying_key = VerifyingKey.from_string(
            bytes.fromhex(public_key_hex),
            curve=SECP256k1,
        )
        return verifying_key.verify(
            bytes.fromhex(signature_hex),
            message.encode("utf-8"),
        )
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

    def sign(self, message: str) -> str:
        return sign_message(self.private_key, message)


@dataclass
class TxInput:
    prev_tx_id: str
    output_index: int
    public_key_hex: str = ""
    signature_hex: str = ""

    def outpoint(self) -> str:
        return f"{self.prev_tx_id}:{self.output_index}"

    def serialize_legacy(self) -> str:
        """
        Legacy txid 계산용.
        signature가 txid 계산에 포함된다.
        """
        return (
            f"{self.prev_tx_id}:{self.output_index}:"
            f"{self.public_key_hex}:{self.signature_hex}"
        )

    def serialize_no_witness(self) -> str:
        """
        SegWit 스타일 txid 계산용.
        signature는 witness로 분리되므로 txid 계산에서 제외된다.
        """
        return f"{self.prev_tx_id}:{self.output_index}"


@dataclass
class TxOutput:
    recipient: str
    amount: int

    def serialize(self) -> str:
        return f"{self.recipient}:{self.amount}"


@dataclass
class Transaction:
    inputs: List[TxInput]
    outputs: List[TxOutput]
    meta: str = ""

    def signing_payload(self) -> str:
        """
        서명 대상.
        signature 자체는 당연히 서명 대상에서 제외한다.
        """
        input_part = "|".join(tx_input.outpoint() for tx_input in self.inputs)
        output_part = "|".join(output.serialize() for output in self.outputs)
        return f"IN[{input_part}]OUT[{output_part}]META[{self.meta}]"

    def signing_message(self) -> str:
        return sha256_str(self.signing_payload())

    def legacy_payload(self) -> str:
        """
        Legacy 스타일 transaction serialization.
        signature가 txid 계산에 포함된다.
        """
        input_part = "|".join(tx_input.serialize_legacy() for tx_input in self.inputs)
        output_part = "|".join(output.serialize() for output in self.outputs)
        return f"IN[{input_part}]OUT[{output_part}]META[{self.meta}]"

    def segwit_base_payload(self) -> str:
        """
        SegWit 스타일 base transaction.
        witness(signature/public key)는 분리되므로 txid 계산에서 제외된다.
        """
        input_part = "|".join(tx_input.serialize_no_witness() for tx_input in self.inputs)
        output_part = "|".join(output.serialize() for output in self.outputs)
        return f"IN[{input_part}]OUT[{output_part}]META[{self.meta}]"

    def witness_payload(self) -> str:
        """
        SegWit에서 witness에 해당하는 데이터.
        실제 비트코인에서는 witness가 별도 영역에 저장된다.
        """
        witness_part = "|".join(
            f"{tx_input.public_key_hex}:{tx_input.signature_hex}"
            for tx_input in self.inputs
        )
        return f"WITNESS[{witness_part}]"

    def legacy_txid(self) -> str:
        """
        signature 포함 txid.
        signature가 조금이라도 바뀌면 txid도 바뀐다.
        """
        return sha256_str(self.legacy_payload())

    def segwit_txid(self) -> str:
        """
        witness 제외 txid.
        signature가 바뀌어도 txid는 변하지 않는다.
        """
        return sha256_str(self.segwit_base_payload())

    def wtxid(self) -> str:
        """
        witness까지 포함한 transaction id.
        실제 SegWit에는 txid와 wtxid 개념이 나뉜다.
        """
        return sha256_str(self.segwit_base_payload() + self.witness_payload())


def sign_transaction(tx: Transaction, wallet: Wallet) -> None:
    message = tx.signing_message()
    signature_hex = wallet.sign(message)

    for tx_input in tx.inputs:
        tx_input.public_key_hex = wallet.public_key_hex
        tx_input.signature_hex = signature_hex


def validate_transaction_signature(tx: Transaction) -> bool:
    message = tx.signing_message()

    for tx_input in tx.inputs:
        if not tx_input.public_key_hex:
            return False

        if not tx_input.signature_hex:
            return False

        if not verify_signature(
            public_key_hex=tx_input.public_key_hex,
            message=message,
            signature_hex=tx_input.signature_hex,
        ):
            return False

    return True


def mutate_signature_format(signature_hex: str) -> str:
    """
    학습용 malleation.

    실제 ECDSA 서명 malleability는 DER 인코딩, s값 변형 등 더 정교한 형태로 발생한다.
    여기서는 '검증 로직은 기존 signature를 사용한다고 가정'하지 않고,
    단순히 signature 필드에 표현상 불필요한 태그를 붙여 txid가 바뀌는 현상만 보여준다.

    단, 이 변형 signature는 실제 검증에는 실패할 수 있으므로,
    아래 예제에서는 'txid 계산 구조상 signature 포함 여부'를 보여주는 데 집중한다.
    """
    return signature_hex + "_MALLEATED"


def main() -> None:
    alice = Wallet("Alice")
    bob = Wallet("Bob")

    tx = Transaction(
        inputs=[
            TxInput(
                prev_tx_id="prev_tx_abc123",
                output_index=0,
            )
        ],
        outputs=[
            TxOutput(
                recipient=bob.public_key_hex,
                amount=10,
            )
        ],
        meta="alice-to-bob",
    )

    sign_transaction(tx, alice)

    print("[*] Original transaction")
    print(f"  valid signature : {validate_transaction_signature(tx)}")
    print(f"  legacy txid     : {tx.legacy_txid()}")
    print(f"  segwit txid     : {tx.segwit_txid()}")
    print(f"  wtxid           : {tx.wtxid()}")

    original_legacy_txid = tx.legacy_txid()
    original_segwit_txid = tx.segwit_txid()
    original_wtxid = tx.wtxid()

    print("\n[*] Change only signature/witness field")
    tx.inputs[0].signature_hex = mutate_signature_format(tx.inputs[0].signature_hex)

    print(f"  valid signature : {validate_transaction_signature(tx)}")
    print(f"  legacy txid     : {tx.legacy_txid()}")
    print(f"  segwit txid     : {tx.segwit_txid()}")
    print(f"  wtxid           : {tx.wtxid()}")

    print("\n[Comparison]")
    print(f"  legacy txid changed? {original_legacy_txid != tx.legacy_txid()}")
    print(f"  segwit txid changed? {original_segwit_txid != tx.segwit_txid()}")
    print(f"  wtxid changed?       {original_wtxid != tx.wtxid()}")

    print("\n[*] Change actual transaction output amount")
    tx.outputs[0].amount = 999

    print(f"  legacy txid     : {tx.legacy_txid()}")
    print(f"  segwit txid     : {tx.segwit_txid()}")
    print(f"  wtxid           : {tx.wtxid()}")
    print(f"  signature valid : {validate_transaction_signature(tx)}")

    print("\n[Meaning]")
    print("  - Changing witness/signature changes legacy txid and wtxid.")
    print("  - Changing witness/signature does not change SegWit txid.")
    print("  - Changing real transaction contents changes SegWit txid too.")
    print("  - Tampering output amount breaks signature validation.")


if __name__ == "__main__":
    main()