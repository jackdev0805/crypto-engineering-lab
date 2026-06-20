# Toy Wallet UTXO Blockchain

이 코드는 UTXO 기반 toy 블록체인 예제를 한 단계 더 정리하여, Wallet과 Blockchain의 역할을 분리한 학습용 구현이다.

## 이번 단계의 핵심

이전 버전에서는 트랜잭션 생성과 서명 로직이 Blockchain 클래스 안에 들어 있었다.  
하지만 실제 구조에서는 private key를 가지고 있는 주체는 블록체인이 아니라 사용자 지갑(Wallet)이다.

이번 버전에서는 역할을 다음과 같이 분리했다.

- Wallet
  - private key / public key 보유
  - 잔액 조회
  - 트랜잭션 생성
  - 서명 수행

- Blockchain
  - 트랜잭션 검증
  - 블록 생성 및 추가
  - UTXO 관리
  - 체인 검증

## 왜 이렇게 나누는가

블록체인은 private key를 절대 알지 못한다.  
블록체인이 볼 수 있는 것은 다음뿐이다.

- public key
- signature
- transaction data

즉:

- 서명은 Wallet이 한다
- 검증은 Blockchain이 한다

이 역할 분리가 암호화폐 구조의 핵심이다.

## 포함된 개념

- Wallet
- 공개키 / 개인키
- 디지털 서명
- UTXO
- 블록
- Proof of Work
- 트랜잭션 검증
- 체인 재검증

## 실행

```bash
pip install -r requirements.txt
python main.py
```
