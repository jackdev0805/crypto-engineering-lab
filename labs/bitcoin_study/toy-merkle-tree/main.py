from __future__ import annotations

import hashlib
from typing import List


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_str(data: str) -> str:
    return sha256_hex(data.encode("utf-8"))


def merkle_root(items: List[str]) -> str:
    """
    문자열 리스트를 받아 Merkle Root를 계산한다.

    학습용 단순화:
    - 각 item은 이미 tx_id 같은 해시 문자열이라고 가정한다.
    - 실제 비트코인은 double SHA-256, little-endian 처리 등이 들어간다.
    """
    if not items:
        return ""

    current_level = items[:]

    while len(current_level) > 1:
        next_level = []

        for i in range(0, len(current_level), 2):
            left = current_level[i]

            if i + 1 < len(current_level):
                right = current_level[i + 1]
            else:
                # 홀수 개면 마지막 노드를 복제한다.
                right = left

            parent = sha256_str(left + right)
            next_level.append(parent)

        current_level = next_level

    return current_level[0]


def build_merkle_levels(items: List[str]) -> List[List[str]]:
    """
    Merkle Tree의 각 level을 출력/학습용으로 반환한다.
    levels[0] = leaf level
    levels[-1] = root level
    """
    if not items:
        return []

    levels = [items[:]]
    current_level = items[:]

    while len(current_level) > 1:
        next_level = []

        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            next_level.append(sha256_str(left + right))

        levels.append(next_level)
        current_level = next_level

    return levels


def print_levels(levels: List[List[str]]) -> None:
    for depth, level in enumerate(levels):
        print(f"\n[Level {depth}]")
        for index, value in enumerate(level):
            print(f"  {index}: {value}")


def main() -> None:
    transactions = [
        "Satoshi -> Alice : 30",
        "Alice -> Bob : 10",
        "Bob -> Charlie : 4",
        "Miner1 coinbase : 50",
        "Alice -> Dave : 2",
    ]

    tx_ids = [sha256_str(tx) for tx in transactions]

    print("[Transactions]")
    for tx, tx_id in zip(transactions, tx_ids):
        print(f"  {tx}")
        print(f"    tx_id: {tx_id}")

    levels = build_merkle_levels(tx_ids)
    print_levels(levels)

    root = merkle_root(tx_ids)
    print(f"\n[Merkle Root]\n  {root}")

    print("\n[Tampering Test]")
    tampered_transactions = transactions[:]
    tampered_transactions[1] = "Alice -> Bob : 999"

    tampered_tx_ids = [sha256_str(tx) for tx in tampered_transactions]
    tampered_root = merkle_root(tampered_tx_ids)

    print(f"  original root: {root}")
    print(f"  tampered root: {tampered_root}")
    print(f"  changed? {root != tampered_root}")


if __name__ == "__main__":
    main()