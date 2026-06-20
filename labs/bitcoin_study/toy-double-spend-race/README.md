# Toy Double Spend Race

이 예제는 UTXO 모델에서 double spend race가 어떻게 발생하고, 블록 확정에 따라 어떤 트랜잭션이 살아남는지 학습하기 위한 코드다.

## 핵심 상황

Satoshi가 50짜리 UTXO 하나를 가지고 있다고 하자.

Satoshi는 같은 UTXO를 사용해서 두 개의 트랜잭션을 만들 수 있다.

```text
tx1: Satoshi → Bob 30
tx2: Satoshi → Charlie 30
```
