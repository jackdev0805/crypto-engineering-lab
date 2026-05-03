# Toy Fork Resolution

이 예제는 두 노드가 같은 높이에서 서로 다른 블록을 채굴했을 때 발생하는 fork와, 이후 더 긴 체인이 선택되면서 한쪽 거래가 rollback되는 과정을 학습하기 위한 코드다.

## 이번 단계의 핵심

이전 예제에서는 한 노드가 블록을 채굴하고, 다른 노드가 그 블록을 받아들이는 단순한 double spend race를 다뤘다.

이번 예제에서는 더 현실적인 상황을 본다.

```text
NodeA mines block with tx1
NodeB mines block with tx2

둘 다 같은 높이의 유효한 블록이다.
즉, 체인이 일시적으로 갈라진다.
```
