# Toy Blockchain

이 코드는 블록체인의 가장 핵심적인 구조를 학습용으로 단순화해 구현한 예제다.

## 포함된 개념

- 블록
- 이전 블록 해시 연결
- SHA-256 해시
- nonce
- 간단한 Proof of Work
- 체인 무결성 검증

## 핵심 포인트

### 1. 블록은 이전 블록 해시를 가진다

각 블록은 `previous_hash`를 통해 이전 블록과 연결된다.  
중간 블록 데이터가 바뀌면 그 블록의 해시가 달라지고, 뒤에 이어진 체인도 깨진다.

### 2. 채굴은 nonce를 바꾸며 해시를 반복 계산하는 과정이다

이 예제에서는 해시가 특정 개수의 `0`으로 시작할 때까지 nonce를 증가시킨다.

예:

- difficulty = 4
- 목표 조건: `0000abcd...`

### 3. 실제 비트코인은 조금 더 엄밀하다

실제 비트코인은 문자열 prefix를 직접 보는 것이 아니라,
블록 헤더를 double SHA-256 한 값을 정수로 보고 그것이 target보다 작은지 검사한다.

즉 학습용 예제의:

```python
hash.startswith("0000")
```

는 실제 비트코인의:

```text
    hash < target
```

을 쉽게 보여주기 위한 단순화다.

4. genesis block의 previous_hash

genesis block은 이전 블록이 없기 때문에 null 대신 0000...0000 같은 zero hash를 사용했다.
이 방식이 일반 블록과 자료형을 통일하기 쉽다.

### 실행

```bash
python main.py
```

### 확인할 수 있는 것

    1.	nonce가 계속 증가한다.
    2.	특정 조건을 만족하는 해시가 발견되면 블록이 채굴된다.
    3.	블록 데이터를 바꾸면 체인 검증이 실패한다.

### 이 코드가 의도적으로 생략한 것

    •	트랜잭션 구조
    •	UTXO
    •	디지털 서명
    •	머클트리
    •	네트워크 전파
    •	난이도 조정
    •	longest chain / heaviest chain 규칙
    •	mempool 정책

### 다음 단계 추천

    •	Transaction 클래스 만들기
    •	UTXO 모델 만들기
    •	머클트리 추가하기
    •	서명 검증 붙이기
    •	block header와 block body 분리하기
