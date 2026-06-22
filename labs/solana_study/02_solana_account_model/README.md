# Step 02 - Solana Account Model

## 목표

Solana의 핵심 구조인 Account Model을 Rust 코드로 시뮬레이션하면서 이해한다.

이번 단계에서는 다음 개념을 학습한다.

- Account
- Program
- Owner
- Lamports
- Data
- Executable
- Account 데이터 수정 권한
- Lamports 전송

---

## 실행 방법

    cargo run

---

## 프로젝트 구조

    solana-study/
    ├─ Cargo.toml
    ├─ README.md
    └─ src/
       └─ main.rs

---

## Solana Account란?

Solana에서는 모든 것이 Account이다.

Account는 단순한 지갑이 아니다.

Account는 다음 정보를 저장한다.

    Account
    ├─ address
    ├─ owner
    ├─ lamports
    ├─ data
    └─ executable

---

## Account 구조체

이번 예제에서는 Solana Account를 단순화하여 다음과 같이 구현했다.

```rust
struct Account {
    address: String,
    owner: String,
    lamports: u64,
    data: Vec<u8>,
    executable: bool,
}
```

---

## Address

Account의 주소이다.

실제 Solana에서는 Public Key가 된다.

예제에서는 문자열로 단순 표현하였다.

예시:

```text
AliceWallet111
CounterAccount222
```

---

## Owner

Account를 소유한 Program이다.

Solana에서 매우 중요한 규칙이 있다.

> Account의 Data는 Owner Program만 수정할 수 있다.

예시:

```rust
let counter_account = Account::new(
    "CounterAccount222".to_string(),
    counter_program.clone(),
    500,
    vec![0],
);
```

위 Account의 Owner는 CounterProgram이다.

따라서 CounterProgram만 Data를 수정할 수 있다.

---

## Lamports

Lamports는 SOL의 최소 단위이다.

실제 비율:

```text
1 SOL = 1,000,000,000 Lamports
```

예제에서는 단순화를 위해 작은 숫자를 사용한다.

```rust
1_000
500
```

Rust에서는 숫자 가독성을 위해 `_`를 사용할 수 있다.

```rust
1_000_000
1_000_000_000
```

---

## Data

Account가 저장하는 실제 데이터이다.

실제 Solana에서는 Byte Array 형태로 저장된다.

예제에서는 Counter 값을 저장한다고 가정한다.

초기 상태:

```rust
vec![0]
```

변경 후:

```rust
vec![1]
```

나중에 Anchor에서는 이것을 구조체로 표현한다.

예시:

```rust
#[account]
pub struct Counter {
    pub count: u64,
}
```

---

## Executable

Program Account 여부를 의미한다.

```rust
executable: bool
```

일반 사용자 지갑은:

```text
false
```

Program Account는:

```text
true
```

이다.

이번 예제에서는 단순화를 위해 모두 false로 처리하였다.

---

## Lamports 전송

Account 간 Lamports는 이동할 수 있다.

예제:

```rust
transfer_lamports(
    &mut alice_account,
    &mut counter_account,
    100,
);
```

결과:

```text
Alice   : 1000 → 900
Counter : 500  → 600
```

---

## Data 수정

Data 수정은 아무나 할 수 없다.

예제:

```rust
counter_account.write_data(
    vec![1],
    &counter_program,
);
```

성공.

이유:

```text
CounterProgram == Owner
```

---

반면:

```rust
counter_account.write_data(
    vec![99],
    &system_program,
);
```

실패.

이유:

```text
SystemProgram != Owner
```

---

## 실행 흐름

### 1. Account 생성

```text
Alice Account
Owner = SystemProgram
Lamports = 1000
Data = []
```

```text
Counter Account
Owner = CounterProgram
Lamports = 500
Data = [0]
```

---

### 2. Lamports 전송

```text
Alice → Counter
100 Lamports
```

결과:

```text
Alice = 900
Counter = 600
```

---

### 3. CounterProgram이 Data 수정

```text
[0] → [1]
```

성공.

---

### 4. SystemProgram이 Data 수정 시도

```text
[1] → [99]
```

실패.

Owner가 아니기 때문이다.

---

## Solana와 연결

현재 예제:

```rust
struct Account {
    address: String,
    owner: String,
    lamports: u64,
    data: Vec<u8>,
    executable: bool,
}
```

실제 Solana에서는 개념적으로 다음과 비슷하다.

```text
AccountInfo
├─ key
├─ owner
├─ lamports
├─ data
├─ executable
└─ rent_epoch
```

---

## Anchor와 연결

나중에 Anchor에서는 다음과 같이 Account를 다룬다.

```rust
#[derive(Accounts)]
pub struct Increment<'info> {
    #[account(mut)]
    pub counter: Account<'info, Counter>,
}
```

여기서:

```rust
#[account(mut)]
```

의 의미는

```text
이 Account의 Data를 수정하겠다.
```

라는 뜻이다.

현재 Rust 예제의

```rust
&mut Account
```

와 거의 같은 개념이다.

---

## 이번 단계 핵심 정리

### Account

데이터 저장 공간

### Owner

Data를 수정할 수 있는 Program

### Lamports

SOL의 최소 단위

### Data

Account가 저장하는 실제 데이터

### Executable

Program Account 여부

### 가장 중요한 규칙

```text
Account Data는 Owner Program만 수정 가능
```

---

## 체크리스트

다음 질문에 답할 수 있으면 통과.

- Account란 무엇인가?
- Owner란 무엇인가?
- Lamports란 무엇인가?
- Data란 무엇인가?
- Data는 누가 수정할 수 있는가?
- Lamports 전송과 Data 수정은 무엇이 다른가?
- Vec<u8>는 왜 사용하는가?
- &mut Account가 필요한 이유는 무엇인가?

---

## 다음 단계

Step 03 - Anchor Counter

학습 내용

- Anchor 프로젝트 생성
- #[program]
- #[derive(Accounts)]
- #[account]
- Counter Account
- initialize
- increment
- Solana Program 구조
