# Toy Merkle Tree

이 예제는 블록체인에서 트랜잭션 목록을 하나의 해시값으로 요약하는 Merkle Tree를 학습하기 위한 코드다.

## Merkle Tree란?

Merkle Tree는 여러 개의 데이터를 해시로 묶어 최종적으로 하나의 루트 해시(Merkle Root)를 만드는 트리 구조다.

블록체인에서는 보통 각 트랜잭션의 해시(tx_id)를 leaf node로 두고, 두 개씩 묶어 다시 해시한다.

예:

```text
tx1      tx2      tx3      tx4
 |        |        |        |
h1       h2       h3       h4
  \      /          \      /
   h12              h34
      \            /
        merkle root
```
