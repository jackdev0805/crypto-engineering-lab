# Toy Target Difficulty

이 예제는 이전 단계의 prefix 방식 난이도 조건을 실제 비트코인에 더 가까운 target 비교 방식으로 바꾼 학습용 코드다.

## 이전 방식

이전 toy 예제에서는 난이도를 다음처럼 표현했다.

## Merkle Root 연결

이번 예제에서는 Block Header의 `merkle_root`를 단순 문자열 해시로 대체하지 않고, 해당 블록에 포함된 트랜잭션들의 `tx_id` 목록으로부터 계산한다.

흐름은 다음과 같다.

````text
transactions
→ tx_id list
→ Merkle Tree
→ Merkle Root
→ Block Header
→ Proof of Work

```python
hash.startswith("0000")
````
