# Toy Block Header

이 예제는 Merkle Root를 Block Header에 포함시키고, 블록 해시를 트랜잭션 전체가 아니라 Block Header 기준으로 계산하는 구조를 학습하기 위한 코드다.

## 이번 단계의 핵심

이전 단계에서는 트랜잭션 목록을 직접 다루거나, Merkle Tree를 별도 예제로만 확인했다.

이번 단계에서는 다음 구조를 만든다.

```text
Block
├─ Header
│  ├─ version
│  ├─ previous_hash
│  ├─ merkle_root
│  ├─ timestamp
│  ├─ bits
│  └─ nonce
└─ transactions
```
