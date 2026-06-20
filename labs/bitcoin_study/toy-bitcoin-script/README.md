# Toy Bitcoin Script

이 예제는 Bitcoin Script의 가장 대표적인 잠금/해제 구조인 P2PKH를 단순화해 구현한 학습용 코드다.

---

# 이번 단계의 핵심

이전 예제에서는 UTXO의 소유권을 코드에서 직접 확인했다.

예:

    public key → address 계산
    address == UTXO owner인지 확인
    signature 검증

하지만 실제 비트코인에서는 UTXO 출력에 "잠금 스크립트(Locking Script)"가 들어 있고, 입력 쪽에서 그 잠금을 푸는 "해제 스크립트(Unlocking Script)"를 제시한다.

즉,

    scriptSig + scriptPubKey 실행 결과가 TRUE이면 spend 가능

이라는 구조다.

---

# P2PKH란?

P2PKH는 Pay To Public Key Hash 의 약자다.

의미는 다음과 같다.

    "이 Public Key Hash의 주인만 이 UTXO를 사용할 수 있다."

---

# 구조

## scriptPubKey (잠금 스크립트)

UTXO 출력에 저장되는 조건이다.

    OP_DUP
    OP_HASH160
    <public_key_hash>
    OP_EQUALVERIFY
    OP_CHECKSIG

---

## scriptSig (해제 스크립트)

UTXO를 사용하려는 사람이 제출하는 데이터다.

    <signature>
    <public_key>

---

## 실제 실행 형태

실행 시에는 두 스크립트가 이어진다.

    <signature>
    <public_key>
    OP_DUP
    OP_HASH160
    <public_key_hash>
    OP_EQUALVERIFY
    OP_CHECKSIG

---

# 실행 흐름

## 1. Alice가 UTXO를 받음

Alice의 Public Key Hash로 잠긴 UTXO가 있다고 가정한다.

scriptPubKey:

    OP_DUP
    OP_HASH160
    <Alice public key hash>
    OP_EQUALVERIFY
    OP_CHECKSIG

---

## 2. Alice가 소비하려고 함

Alice는 자신의 증명 정보를 제출한다.

scriptSig:

    <Alice signature>
    <Alice public key>

실행 결과가 TRUE이면 사용 가능하다.

---

## 3. Attacker가 소비하려고 함

Attacker는 자신의 공개키와 서명을 제출한다.

scriptSig:

    <Attacker signature>
    <Attacker public key>

하지만

    hash160(Attacker public key)
    !=
    Alice public key hash

이므로 OP_EQUALVERIFY에서 실패한다.

---

## 4. 거래 내용 변조

Alice가 원래 다음 거래에 서명했다고 하자.

    Alice -> Bob : 10

그런데 누군가가 중간에

    Alice -> Bob : 999

로 바꾸면 메시지 해시가 달라진다.

따라서 OP_CHECKSIG 단계에서 실패한다.

---

# Stack 실행 예시

초기 상태:

    []

---

scriptSig 실행 후:

    [signature, public_key]

---

OP_DUP 실행 후:

    [signature, public_key, public_key]

---

OP_HASH160 실행 후:

    [signature, public_key, hash160(public_key)]

---

public_key_hash push:

    [signature,
     public_key,
     hash160(public_key),
     expected_public_key_hash]

---

OP_EQUALVERIFY 실행 후:

    [signature, public_key]

---

OP_CHECKSIG 실행 후:

    [TRUE]

---

최종적으로 Stack Top이 TRUE이면 spend 성공이다.

---

# 코드에서 봐야 할 부분

## create_p2pkh_script_pubkey()

잠금 스크립트 생성

```python
def create_p2pkh_script_pubkey(public_key_hash: str) -> Script:
    return Script(
        commands=[
            "OP_DUP",
            "OP_HASH160",
            public_key_hash,
            "OP_EQUALVERIFY",
            "OP_CHECKSIG",
        ]
    )
```

---

## create_script_sig()

해제 스크립트 생성

```python
def create_script_sig(signature_hex: str, public_key_hex: str) -> Script:
    return Script(
        commands=[
            signature_hex,
            public_key_hex,
        ]
    )
```

---

## ScriptInterpreter.run()

실제로 두 스크립트를 합쳐 실행

```python
combined_commands = (
    script_sig.commands +
    script_pubkey.commands
)
```

---

# 실제 Bitcoin과의 차이

이 예제는 학습용이다.

실제 Bitcoin은 아래 사항이 추가된다.

- HASH160 = RIPEMD160(SHA256(pubkey))
- DER Signature
- SIGHASH Flag
- Script Number Encoding
- Witness / SegWit
- P2SH
- P2WPKH
- P2WSH
- Taproot
- Schnorr Signature
- Script Execution Limit
- Transaction Digest 규칙

---

# 이번 단계의 의미

이전까지는 Node 코드가 직접 다음을 검사했다.

    address 일치?
    signature 유효?

하지만 실제 Bitcoin은 이런 검사를 코드에 하드코딩하지 않는다.

대신:

    UTXO가 가진 조건(scriptPubKey)

와

    사용자가 제출한 증명(scriptSig)

을 실행한다.

즉,

    Ownership Rule
    ↓
    Script

로 일반화한 것이다.

Bitcoin Script는 결국

    "이 코인을 사용할 수 있는 조건"

을 프로그래밍 언어 형태로 표현한 시스템이라고 볼 수 있다.

---

# 다음 단계

다음 단계에서는 실제 Bitcoin Core를 읽기 전에 반드시 알아야 하는

- Transaction 구조
- txid 생성 방식
- Witness
- SegWit
- 왜 tx malleability 문제가 생겼는가

를 구현해보는 것이 좋다.

특히 SegWit은 지금 만든 Signature 구조가 실제 Bitcoin에서 왜 바뀌게 되었는지를 이해하는 핵심 단계다.
