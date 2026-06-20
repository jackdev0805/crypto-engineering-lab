# Toy UTXO Blockchain

이 코드는 블록체인의 핵심 구조에 더해, 비트코인 스타일의 UTXO 모델을 단순화해 구현한 학습용 예제다.

## 포함된 개념

- 블록
- Proof of Work
- 트랜잭션 입력 / 출력
- UTXO (Unspent Transaction Output)
- 잔액 계산
- 입력 금액 / 출력 금액 검증
- 거스름돈(change) 처리
- 이중 사용 방지의 기초 개념

## 핵심 아이디어

비트코인은 "계정 잔고"를 직접 수정하는 방식이 아니라,
이전 트랜잭션의 출력물을 소비하고 새로운 출력물을 만드는 방식으로 동작한다.

예를 들어 Alice가 30 코인을 가지고 있고 Bob에게 10을 보내면:

- 입력: Alice가 가진 UTXO 하나 이상 사용
- 출력 1: Bob 10
- 출력 2: Alice에게 거스름돈 반환

## 구성 요소

### TransactionInput

이전 트랜잭션의 몇 번째 출력을 소비할지 가리킨다.

### TransactionOutput

수신자와 금액을 정의한다.

### Transaction

입력들과 출력들로 구성된다.

### UTXOSet

아직 소비되지 않은 출력들을 관리한다.

### Blockchain

블록 생성, 채굴, 트랜잭션 검증, UTXO 반영을 담당한다.

## Coinbase 트랜잭션의 고유성 (중요)

이 구현에서는 coinbase 트랜잭션이 매 블록마다 반드시 고유한 `tx_id`를 가지도록 설계하였다.

### 문제 상황

초기 구현에서는 coinbase 트랜잭션이 항상 동일한 구조였다.

- inputs: 없음
- outputs: 동일 (예: Miner1: 50)

이 경우 `tx_id`가 모든 블록에서 동일하게 생성된다.

UTXO는 다음과 같은 key로 관리된다:
tx_id + output_index

따라서 동일한 key가 생성되면서:

- 이전 UTXO가 덮어써지고
- miner 보상이 누적되지 않는 문제가 발생한다

### 해결 방법

coinbase 트랜잭션에 고유한 메타데이터를 추가하였다.

예:

- block height
- miner 정보
- 기타 식별자

이 정보를 `tx_id` 계산에 포함시켜 각 coinbase 트랜잭션이 서로 다른 해시를 가지도록 하였다.

### 실제 비트코인과의 관계

실제 비트코인에서도 coinbase 트랜잭션은 매 블록마다 고유하다.

대표적으로 다음과 같은 요소가 포함된다:

- block height (BIP34)
- coinbase scriptSig
- extra nonce

즉 coinbase는 입력이 없는 대신, 내부 데이터로 고유성을 확보하는 특수한 트랜잭션이다.

## 실행

```bash
python main.py
```
