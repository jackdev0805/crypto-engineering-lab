# Toy Mini Bitcoin Node

이 예제는 지금까지 분리해서 구현했던 여러 개념을 하나의 작은 Bitcoin-like node 구조로 통합한 학습용 구현이다.

## 이번 단계의 목표

이전 단계들에서는 각각의 개념을 따로 실험했다.

- UTXO
- Signature
- Address
- Mempool
- Merkle Root
- Block Header
- Proof of Work
- Miner
- Node validation

이번 예제는 이들을 하나의 흐름으로 연결한다.

```text
Wallet
→ Transaction
→ Node mempool
→ Miner
→ Block
→ Node validation
→ UTXO update
```
