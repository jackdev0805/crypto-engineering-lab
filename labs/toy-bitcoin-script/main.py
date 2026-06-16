from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List

from ecdsa import BadSignatureError, SECP256k1, SigningKey, VerifyingKey


def sha256_str(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def hash160_toy(public_key_hex: str) -> str:
    """
    실제 Bitcoin은 HASH160 = RIPEMD160(SHA256(public_key))를 사용한다.
    여기서는 학습용으로 SHA256 후 앞 40자리만 사용한다.
    """
    return sha256_str(public_key_hex)[:40]


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

    @property
    def public_key_hash(self) -> str:
        return hash160_toy(self.public_key_hex)

    def sign(self, message: str) -> str:
        return sign_message(self.private_key, message)


@dataclass
class Transaction:
    sender: str
    recipient: str
    amount: int
    tx_id: str = ""

    def serialize(self) -> str:
        return f"{self.sender}->{self.recipient}:{self.amount}"

    def signing_message(self) -> str:
        return sha256_str(self.serialize())

    def finalize(self) -> None:
        self.tx_id = sha256_str(self.serialize())


@dataclass
class Script:
    commands: List[str]


class ScriptInterpreter:
    """
    아주 단순화한 Bitcoin Script 실행기.

    지원 opcode:
    - OP_DUP
    - OP_HASH160
    - OP_EQUALVERIFY
    - OP_CHECKSIG

    P2PKH 구조:
    scriptSig:
      <signature> <public_key>

    scriptPubKey:
      OP_DUP OP_HASH160 <public_key_hash> OP_EQUALVERIFY OP_CHECKSIG
    """

    def __init__(self, message: str) -> None:
        self.stack: List[str] = []
        self.message = message

    def run(self, script_sig: Script, script_pubkey: Script) -> bool:
        combined_commands = script_sig.commands + script_pubkey.commands

        try:
            for command in combined_commands:
                if command == "OP_DUP":
                    self.op_dup()
                elif command == "OP_HASH160":
                    self.op_hash160()
                elif command == "OP_EQUALVERIFY":
                    self.op_equalverify()
                elif command == "OP_CHECKSIG":
                    self.op_checksig()
                else:
                    self.stack.append(command)

            return bool(self.stack and self.stack[-1] == "TRUE")

        except ValueError as error:
            print(f"[SCRIPT ERROR] {error}")
            return False

    def op_dup(self) -> None:
        if not self.stack:
            raise ValueError("OP_DUP failed: stack is empty")

        self.stack.append(self.stack[-1])

    def op_hash160(self) -> None:
        if not self.stack:
            raise ValueError("OP_HASH160 failed: stack is empty")

        public_key_hex = self.stack.pop()
        self.stack.append(hash160_toy(public_key_hex))

    def op_equalverify(self) -> None:
        if len(self.stack) < 2:
            raise ValueError("OP_EQUALVERIFY failed: not enough stack items")

        a = self.stack.pop()
        b = self.stack.pop()

        if a != b:
            raise ValueError("OP_EQUALVERIFY failed: values are not equal")

    def op_checksig(self) -> None:
        if len(self.stack) < 2:
            raise ValueError("OP_CHECKSIG failed: not enough stack items")

        public_key_hex = self.stack.pop()
        signature_hex = self.stack.pop()

        if verify_signature(public_key_hex, self.message, signature_hex):
            self.stack.append("TRUE")
        else:
            self.stack.append("FALSE")


def create_p2pkh_script_pubkey(public_key_hash: str) -> Script:
    return Script(
        commands=[
            "OP_DUP",
            "OP_HASH160",
            public_key_hash,
            "OP_EQUALVERIFY",
            "OP_CHECKSIG",
        ]
    )


def create_script_sig(signature_hex: str, public_key_hex: str) -> Script:
    return Script(commands=[signature_hex, public_key_hex])


def main() -> None:
    alice = Wallet("Alice")
    attacker = Wallet("Attacker")

    tx = Transaction(sender="Alice", recipient="Bob", amount=10)
    tx.finalize()

    message = tx.signing_message()

    print("[*] Alice locks UTXO with P2PKH scriptPubKey")
    script_pubkey = create_p2pkh_script_pubkey(alice.public_key_hash)

    print(f"  Alice public_key_hash: {alice.public_key_hash}")
    print(f"  tx message          : {message}")

    print("\n[*] Alice spends it with valid scriptSig")
    alice_signature = alice.sign(message)
    valid_script_sig = create_script_sig(
        signature_hex=alice_signature,
        public_key_hex=alice.public_key_hex,
    )

    interpreter = ScriptInterpreter(message=message)
    result = interpreter.run(valid_script_sig, script_pubkey)
    print(f"  valid spend result: {result}")

    print("\n[*] Attacker tries to spend Alice's UTXO")
    attacker_signature = attacker.sign(message)
    attacker_script_sig = create_script_sig(
        signature_hex=attacker_signature,
        public_key_hex=attacker.public_key_hex,
    )

    interpreter = ScriptInterpreter(message=message)
    result = interpreter.run(attacker_script_sig, script_pubkey)
    print(f"  attacker spend result: {result}")

    print("\n[*] Alice signature is reused after transaction tampering")
    tampered_tx = Transaction(sender="Alice", recipient="Bob", amount=999)
    tampered_tx.finalize()
    tampered_message = tampered_tx.signing_message()

    interpreter = ScriptInterpreter(message=tampered_message)
    result = interpreter.run(valid_script_sig, script_pubkey)
    print(f"  tampered spend result: {result}")


if __name__ == "__main__":
    main()