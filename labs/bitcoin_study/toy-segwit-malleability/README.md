# Toy SegWit & Transaction Malleability

이 예제는 Bitcoin의 transaction malleability 문제와 SegWit의 핵심 아이디어를 단순화해서 이해하기 위한 코드다.

---

# 이번 단계의 핵심

이전까지는 트랜잭션 ID를 계산할 때 입력의 signature도 함께 포함했다.

그런데 signature가 txid 계산에 포함되면 문제가 생긴다.

거래의 실제 의미는 그대로인데, signature 표현이 조금 바뀌는 것만으로 txid가 바뀔 수 있기 때문이다.

이 문제를 transaction malleability라고 한다.

SegWit의 핵심 아이디어 중 하나는 다음이다.

```text
signature / witness 데이터를 txid 계산 대상에서 분리한다.
```

즉:

```text
txid  = witness 제외한 base transaction hash
wtxid = witness 포함한 full transaction hash
```

---

# 왜 txid가 바뀌면 문제가 되는가?

예를 들어 Alice가 Bob에게 송금하는 거래 tx1을 만들었다고 하자.

```text
tx1: Alice → Bob
txid = abc123
```

Bob은 이 txid를 참조해서 다음 거래 tx2를 만들 수 있다.

```text
tx2 input = abc123:0
```

그런데 누군가 tx1의 signature 표현을 살짝 바꿔서 tx1의 의미는 그대로인데 txid만 바꿀 수 있다면 문제가 생긴다.

```text
tx1 의미 동일
기존 txid: abc123
변경 txid: def456
```

그러면 tx2가 참조하던 `abc123:0`은 더 이상 실제 확정된 txid와 맞지 않게 된다.

즉 후속 거래가 깨질 수 있다.

---

# Legacy txid

Legacy 방식에서는 signature가 transaction serialization 안에 들어간다.

이 예제에서는 다음 함수가 legacy txid를 만든다.

```python
def legacy_txid(self) -> str:
    return sha256_str(self.legacy_payload())
```

그리고 `legacy_payload()` 안에는 input의 signature가 포함된다.

```python
def serialize_legacy(self) -> str:
    return (
        f"{self.prev_tx_id}:{self.output_index}:"
        f"{self.public_key_hex}:{self.signature_hex}"
    )
```

따라서 signature가 바뀌면 legacy txid도 바뀐다.

---

# SegWit txid

SegWit 스타일에서는 signature를 witness 영역으로 분리한다.

이 예제에서는 다음 함수가 SegWit 스타일 txid를 만든다.

```python
def segwit_txid(self) -> str:
    return sha256_str(self.segwit_base_payload())
```

그리고 `segwit_base_payload()`는 signature를 포함하지 않는다.

```python
def serialize_no_witness(self) -> str:
    return f"{self.prev_tx_id}:{self.output_index}"
```

따라서 signature가 바뀌어도 SegWit txid는 바뀌지 않는다.

---

# wtxid

SegWit에서는 witness까지 포함한 ID도 필요하다.

이 예제에서는 이를 `wtxid()`로 표현한다.

```python
def wtxid(self) -> str:
    return sha256_str(self.segwit_base_payload() + self.witness_payload())
```

즉:

```text
txid  = witness 제외
wtxid = witness 포함
```

---

# 실행

```bash
pip install -r requirements.txt
python main.py
```

루트 폴더에서 실행한다면:

```bash
pip install -r labs/toy-segwit-malleability/requirements.txt
python labs/toy-segwit-malleability/main.py
```

---

# 실행 결과에서 봐야 할 것

## 1. 원본 거래

처음에는 다음 값들이 출력된다.

```text
legacy txid
segwit txid
wtxid
```

## 2. signature 필드만 변경

signature 필드만 변경하면:

```text
legacy txid changed? True
segwit txid changed? False
wtxid changed? True
```

이렇게 나와야 한다.

의미:

- legacy txid는 signature를 포함하므로 바뀐다
- segwit txid는 signature를 제외하므로 안 바뀐다
- wtxid는 witness를 포함하므로 바뀐다

## 3. 실제 거래 내용 변경

출력 금액을 바꾸면:

```text
amount 10 → 999
```

이건 witness만 바뀐 것이 아니라 거래 자체의 의미가 바뀐 것이다.

따라서 SegWit txid도 바뀐다.

그리고 기존 signature는 더 이상 현재 거래 내용에 대한 서명이 아니므로 검증이 실패한다.

---

# 중요한 주의점

이 예제의 `mutate_signature_format()`은 실제 ECDSA malleability를 정확히 구현한 것이 아니다.

실제 Bitcoin의 transaction malleability는 다음 요소들과 관련된다.

- DER signature encoding
- ECDSA의 s값 malleability
- scriptSig 변형 가능성
- sighash 계산 방식

이 예제는 그중 핵심 구조만 보여준다.

```text
signature가 txid 계산에 들어가면 txid가 흔들릴 수 있다.
signature를 witness로 분리하면 txid가 안정된다.
```

---

# SegWit의 핵심 의미

SegWit은 단순히 수수료를 낮추거나 블록 용량을 늘리는 기능만이 아니다.

중요한 구조적 변화는 다음이다.

```text
트랜잭션의 효과를 정의하는 데이터와
그 효과를 승인하는 서명 데이터를 분리한다.
```

즉:

```text
base transaction = 누가 무엇을 어디로 보내는가
witness          = 그 행동을 승인했다는 증명
```

이렇게 분리하면 txid는 base transaction에 의해 고정된다.

---

# 이번 단계의 의미

이전 단계까지는 다음을 배웠다.

```text
UTXO를 쓰려면 signature가 필요하다.
```

이번 단계에서는 한 단계 더 나아간다.

```text
signature가 어디에 포함되느냐도 중요하다.
```

signature를 txid에 포함하면 거래 ID가 흔들릴 수 있다.

signature를 witness로 분리하면 거래 ID가 안정된다.

---

# 실제 Bitcoin과의 차이

이 코드는 학습용이며 실제 Bitcoin과는 차이가 있다.

생략한 것:

- 실제 transaction serialization
- double SHA-256
- little-endian txid 표현
- DER signature
- SIGHASH flag
- scriptCode
- witness stack
- P2WPKH
- P2WSH
- Taproot / Schnorr
- BIP143 digest algorithm

---

# 다음 단계

다음 단계에서는 실제 Bitcoin transaction 구조를 조금 더 구체적으로 볼 수 있다.

추천 순서:

1. Legacy transaction 구조
2. SegWit transaction 구조
3. input / output serialization
4. txid vs wtxid
5. Bitcoin Core에서 transaction 관련 코드 읽기
