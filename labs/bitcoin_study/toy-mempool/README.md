# Toy Mempool

이 예제는 블록체인에서 mempool이 어떤 역할을 하는지 학습하기 위한 코드다.

## Mempool이란?

Mempool은 아직 블록에 포함되지 않은 트랜잭션들이 임시로 대기하는 공간이다.

사용자가 트랜잭션을 만들면 그 트랜잭션이 즉시 블록에 들어가는 것이 아니다.

일반적인 흐름은 다음과 같다.

```text
Wallet creates transaction
→ Node validates transaction
→ Transaction enters mempool
→ Miner selects transactions
→ Block is mined
→ Confirmed transactions are removed from mempool
```
