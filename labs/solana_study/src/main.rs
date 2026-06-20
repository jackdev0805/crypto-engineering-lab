#[derive(Debug)]
struct Wallet {
    owner: String,
    sol_balance: u64,
}

impl Wallet {
    fn new(owner: String, sol_balance: u64) -> Self {
        Self {
            owner,
            sol_balance,
        }
    }

    fn deposit(&mut self, amount: u64) {
        self.sol_balance += amount;
    }

    fn withdraw(&mut self, amount: u64) -> Result<(), String> {
        if self.sol_balance < amount {
            return Err("잔액이 부족합니다.".to_string());
        }

        self.sol_balance -= amount;
        Ok(())
    }
}

fn transfer(from: &mut Wallet, to: &mut Wallet, amount: u64) -> Result<(), String> {
    from.withdraw(amount)?;
    to.deposit(amount);
    Ok(())
}

fn main() {
    let mut alice = Wallet::new("Alice".to_string(), 100);
    let mut bob = Wallet::new("Bob".to_string(), 50);

    println!("초기 상태");
    println!("{:?}", alice);
    println!("{:?}", bob);

    let result = transfer(&mut alice, &mut bob, 120);

    match result {
        Ok(_) => println!("전송 성공"),
        Err(e) => println!("전송 실패: {}", e),
    }

    println!("전송 후 상태");
    println!("{:?}", alice);
    println!("{:?}", bob);
}