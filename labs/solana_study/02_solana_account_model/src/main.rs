#[derive(Debug)]
struct Account {
    address: String,
    owner: String,
    lamports: u64,
    data: Vec<u8>,
    executable: bool,
}

impl Account {
    fn new(address: String, owner: String, lamports: u64, data: Vec<u8>) -> Self {
        Self {
            address,
            owner,
            lamports,
            data,
            executable: false
        }
    }

    fn print_info(&self) {
        println!("Account Address   : {}", self.address);
        println!("Owner Program     : {}", self.owner);
        println!("Lamports          : {}", self.lamports);
        println!("Data              : {:?}", self.data);
        println!("Executable        : {}", self.executable);
        println!("----------------------------------");
    }

    fn deposit_lamports(&mut self, amount: u64) {
        self.lamports += amount;
    }

    fn withdraw_lamports(&mut self, amount: u64) -> Result<(), String> {
        if self.lamports < amount {
            return Err("lamports 부족".to_string());
        }

        self.lamports -= amount;
        Ok(())
    }

    fn write_data(&mut self, new_data: Vec<u8>, signer_program: &str) -> Result<(), String> {
        if self.owner != signer_program {
            return Err("이 프로그램은 해당 Account의 owner가 아닙니다.".to_string());
        }

        self.data = new_data;
        Ok(())
    }
}

fn transfer_lamports(
    from: &mut Account,
    to: &mut Account,
    amount: u64
) -> Result<(), String> {
    from.withdraw_lamports(amount)?;
    to.deposit_lamports(amount);
    Ok(())
}

fn main() {
    let system_program = "SystemProgram".to_string();
    let counter_program = "CounterProgram".to_string();

    let mut alice_account = Account::new(
        "AliceWallet111".to_string(),
        system_program.clone(),
        1_000,
        vec![],
    );

    let mut counter_account = Account::new(
        "CounterAccount222".to_string(),
        counter_program.clone(),
        500,
        vec![0]
    );

    println!("초기 Account 상태");
    alice_account.print_info();
    counter_account.print_info();

    println!("Alice가 Counter Account에 100 lamports 전송");
    let result = transfer_lamports(&mut alice_account, &mut counter_account, 100);

    match result {
        Ok(_) => println!("lamports 전송 성공"),
        Err(e) => println!("lamports 전송 실패: {}", e),
    }

    println!("\nCounterProgram이 Counter Account의 data 수정");
    let result = counter_account.write_data(vec![1], &counter_program);

    match result {
        Ok(_) => println!("data 수정 성공"),
        Err(e) => println!("data 수정 실패: {}", e),
    }

    println!("\nSystemProgram이 Counter Account의 data 수정 시도");
    let result = counter_account.write_data(vec![99], &system_program);
    match result {
        Ok(_) => println!("data 수정 성공"),
        Err(e) => println!("data 수정 실패: {}", e),
    }

    println!("\n최종 Account 상태");
    alice_account.print_info();
    counter_account.print_info();
}