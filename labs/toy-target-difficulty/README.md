# Toy Target Difficulty

이 예제는 이전 단계의 prefix 방식 난이도 조건을 실제 비트코인에 더 가까운 target 비교 방식으로 바꾼 학습용 코드다.

## 이전 방식

이전 toy 예제에서는 난이도를 다음처럼 표현했다.

```python
hash.startswith("0000")
```
