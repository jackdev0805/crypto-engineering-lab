Step 01 - Rust Basics

학습 목표

Solana 개발에 필요한 Rust 기초 문법을 익힌다.

이번 단계에서는 다음 내용을 학습한다.

- 변수와 가변성(mut)
- 구조체(struct)
- 구현 블록(impl)
- 소유권(Ownership)
- 참조(Reference)
- 가변 참조(Mutable Reference)
- Result
- match
- 간단한 송금 로직

⸻

프로젝트 실행

cargo run

⸻

프로젝트 구조

solana-study/
├─ Cargo.toml
├─ README.md
└─ src/
└─ main.rs

⸻

예제 시나리오

Alice가 100 SOL을 가지고 있다.

Bob이 50 SOL을 가지고 있다.

Alice가 Bob에게 30 SOL을 송금한다.

전송 성공 시:

Alice : 70
Bob : 80

이 된다.

⸻

Wallet 구조체

struct Wallet {
owner: String,
sol_balance: u64,
}

지갑 소유자와 잔액을 저장한다.

실제 Solana에서는 Account가 데이터를 저장하지만,

현재는 Rust 학습을 위해 Wallet 구조체를 사용한다.

⸻

impl

impl Wallet {
fn deposit(&mut self, amount: u64) {
self.sol_balance += amount;
}
}

impl은 구조체에 기능을 추가하는 문법이다.

객체지향 언어의 멤버 함수와 비슷한 개념이다.

⸻

& 와 &mut

읽기 전용 참조

let wallet_ref = &alice;

수정 가능한 참조

let wallet_ref = &mut alice;

송금 함수는 잔액을 수정해야 하므로

fn transfer(
from: &mut Wallet,
to: &mut Wallet,
amount: u64,
)

와 같이 작성한다.

⸻

Result

실패할 수 있는 함수는 Result를 반환한다.

fn withdraw(
&mut self,
amount: u64,
) -> Result<(), String>

성공

Ok(())

실패

Err("잔액 부족".to_string())

⸻

? 연산자

from.withdraw(amount)?;

의 의미는

match from.withdraw(amount) {
Ok(v) => v,
Err(e) => return Err(e),
}

와 거의 동일하다.

에러가 발생하면 즉시 함수를 종료한다.

⸻

match

match result {
Ok(\_) => println!("전송 성공"),
Err(e) => println!("전송 실패: {}", e),
}

Result를 처리할 때 가장 많이 사용하는 문법이다.

⸻

이번 단계에서 반드시 이해해야 할 내용

1. mut

let x = 10;
let mut y = 20;

- x는 수정 불가
- y는 수정 가능

⸻

2. 구조체

struct Wallet

여러 데이터를 하나로 묶는다.

⸻

3. impl

구조체에 함수를 추가한다.

⸻

4. 참조

&Wallet

읽기만 가능

&mut Wallet

수정 가능

⸻

5. Result

성공 또는 실패를 표현한다.

⸻

6. ?

에러 전파를 쉽게 해준다.

⸻

Solana와의 연결

현재 코드

fn transfer(
from: &mut Wallet,
to: &mut Wallet,
amount: u64,
)

나중에 Solana에서는 다음과 비슷한 형태가 된다.

#[derive(Accounts)]
pub struct Transfer<'info> { #[account(mut)]
pub sender: Account<'info, UserAccount>, #[account(mut)]
pub receiver: Account<'info, UserAccount>,
}

즉 지금 배우는 Rust 문법은

Solana Account를 이해하기 위한 준비 과정이다.

⸻

체크리스트

다음 질문에 답할 수 있으면 통과.

- struct는 왜 사용하는가?
- impl은 무엇인가?
- &와 &mut의 차이는 무엇인가?
- Result는 왜 필요한가?
- ? 연산자는 무엇을 하는가?
- transfer 함수에서 &mut이 필요한 이유는 무엇인가?

⸻

다음 단계

Step 02 - Solana Account Model

학습 내용

- Account
- Program
- Owner
- Lamports
- Data
- Executable
- Rent
- PDA 기초
