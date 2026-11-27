# Payments module: design

Day 3 exercise: a payments module with a `PaymentProcessor` Protocol and three implementations, using composition. Payments are **simulated**: balances live in local text files, and no real money moves.

## 1. The Protocol

```python
class PaymentProcessor(Protocol):
    proc_name: str
    def charge(self, amount: int) -> tuple[str, int]: ...
```

- `proc_name`: a short name for the processor (`"wallet"`, `"upi"`, `"card"`), used in the ledger. Declaring it in the Protocol means mypy checks that every processor provides it, so `Checkout` can rely on it.
- `charge(amount)` takes the amount in **paise** (an `int`, never a float) and returns **two values**: the **transaction ID** and the **total amount actually deducted** (for a card, `amount + fee`).
- `refund` is left out for now (YAGNI). It may be added later, possibly as a separate, smaller Protocol (interface segregation), since not every processor has to support refunds.

## 2. The three processors

Each processor **has a** `BalanceStore` (composition), which holds the shared file logic, so it isn't written three times (DRY).

Each processor is created with a `BalanceStore` (dependency injection) and its own **number** (a `str`: wallet number, UPI ID or card number):

```python
WalletProcessor(BalanceStore(Path("wallet.txt")), wallet_no="W77")
```

Numbers are stored as **`str`, not `int`**: they're identifiers, not quantities (no maths is done on them, and an `int` would drop leading zeros).

| Processor | ID prefix | What makes it different |
|---|---|---|
| `CardProcessor` | `card-` | adds a **2% fee** on top of the amount; `amount + fee` is deducted from the balance |
| `UPIProcessor` | `upi-` | a **per-transaction limit** of ₹1,00,000 = `10_000_000` paise, checked **before** the balance is touched |
| `WalletProcessor` | `wallet-` | the plain balance check: no fee, no limit |

**Card fee:** calculated with integers only, as `amount // 50` (2%), **rounded down**. So any amount under 50 paise has **no fee**. (Decision: rounding down is acceptable; floats are never used for money.)

**UPI limit:** the limit is **inclusive**: exactly `10_000_000` paise is allowed, `10_000_001` is declined.

**`BalanceStore`** (a helper class each processor composes):
- created with the **path** of its balance file (passed in, not hard-coded)
- the file holds one integer: the balance **in paise** (e.g. `500000` = ₹5,000)
- `read_balance() -> int`: returns the balance. Raises `BalanceError` if the file can't be read, isn't a whole number, or is **negative** (decision: a negative balance means the file is broken; overdrafts aren't supported).
- `deduct(amount) -> int`: checks there's enough (paying **exactly** the whole balance is allowed), writes the new balance, and **returns** it. If there isn't enough → `PaymentDeclined`, and the file is **unchanged**.

**Flow of `charge(amount)`:** check its own rules (limit/fee) → deduct (which checks the balance) → return a new transaction ID.

### Transaction IDs
- Format: `{type}-{number}-{counter}`, e.g. `wallet-W77-1`, `upi-rishab@upi-3`.
- Built by one helper function, `give_txn_id(processor_type, processor_no, txn_counter)` (DRY). It's a pure function: values in, string out.
- Each processor instance keeps its own `txn_counter`, starting at 0 and increased by 1 per successful charge.
- **Card numbers are masked:** a card ID contains **only the last 4 digits** of the card number, e.g. `card-4242-1`. A full card number must never be written into IDs, logs or the ledger.

## 3. `Checkout` (the composing class)

```python
Checkout(processor: PaymentProcessor, ledger_path: Path)
```

- **Has a** processor (composition) and the **path** to a ledger file. Both are passed in (dependency injection).
- `pay(amount)`:
  1. **validates** the amount (see section 4). This happens here, once, for every processor (DRY).
  2. **delegates** the payment: `self.processor.charge(amount)`
  3. **records** the transaction in the ledger
  4. returns the transaction ID
- Adding a new processor (e.g. `CryptoProcessor`) needs **no change** to `Checkout` (open/closed principle).

### Ledger format
Appended to the ledger file (opened in `"a"` mode inside `with`, once per transaction). One JSON object per line:

```json
{"time": "2026-11-26T13:05:47.096077+00:00", "txn_id": "card-4242-1", "processor": "card", "amount": 1020}
```

| Field | Value |
|---|---|
| `time` | UTC timestamp: `datetime.now(timezone.utc).isoformat()` |
| `txn_id` | the ID returned by `charge()` |
| `processor` | the processor's `proc_name` |
| `amount` | the **total deducted** from the balance, in paise. For a card, this **includes the 2% fee** (decision: the ledger matches the balance change, so the two can always be reconciled) |

- The entry is written **only after `charge()` succeeds**. A declined payment, or an invalid amount, leaves **no** ledger line.
- Verified: wallet ₹5 + card ₹10 (+ ₹0.20 fee) took the balance from 100000 to 98480, and the ledger holds exactly 2 lines totalling 1520.

## 4. Errors

Custom exceptions:

```
PaymentError                      base class for every payment problem
├── AmountError (also ValueError) the amount is invalid: caught by `except PaymentError` AND `except ValueError`
├── BalanceError                  the balance file is missing, unreadable, not a number, or negative
└── PaymentDeclined               not enough balance, or over the UPI limit
```

| Situation | Raised by | Exception |
|---|---|---|
| amount ≤ 0 | `Checkout.pay` | `AmountError` |
| amount not an `int` (e.g. `10.5`, `10.0`, `"100"`, `None`), or a `bool` (`True`/`False`, because `bool` is a subclass of `int`) | `Checkout.pay`, checked **before** the `<= 0` check | `TypeError`, naming the type received |
| not enough balance | `BalanceStore.deduct` | `PaymentDeclined` |
| over the UPI limit | `UPIProcessor.charge` | `PaymentDeclined` |
| balance file missing / unreadable | `BalanceStore.read_balance` | `BalanceError` (the original `OSError` attached with `from e`) |
| balance file isn't a whole number | `BalanceStore.read_balance` | `BalanceError` (the original `ValueError` attached) |
| balance file is negative | `BalanceStore.read_balance` | `BalanceError` |

- After a **declined** payment: nothing is recorded in the ledger, and the balance is **unchanged**.
- Error messages include the file path and the offending value (shown with `!r`), so the reader knows exactly what to fix.

### Open decisions
- **Should `BalanceStore.deduct` reject `amount <= 0` itself?** Right now only `Checkout` checks, so calling `deduct(-500)` directly would *add* money. Options: validate only at the boundary (`Checkout`), or have every class protect itself.

## 5. Testing plan
- **Normal:** each processor's ID prefix; IDs are unique; the balance drops by exactly the amount (plus the fee for card)
- **Edge:** 1 paisa; exactly at the UPI limit (allowed) and 1 above (declined); charging exactly the whole balance
- **Invalid input:** `0`, negative, `10.5`, `"100"`, `True`
- **Failures:** decline → nothing in the ledger, balance unchanged; missing or corrupt balance file
- **`Checkout` alone:** with **fake** processors (always succeeds / always declines)
- **Types:** `mypy --strict` passes; all three processors are accepted as a `PaymentProcessor`
- **Coverage:** above 80% (Day 3 Verify)
- Tests use pytest's `tmp_path`, so the real balance files are never touched.

## Known limitations
- No protection against a crash **between** reading and writing a balance, or two payments at once. Real systems use a database for this (covered later in the programme).
- deduct() function in BalanceStore opens the file in "w" mode which empties the file first and then writes the input onto the file. If the writing line doesnt get executed due to an error we end up with an empty balance file.
- **Money taken but not recorded:** if writing the ledger fails **after** `charge()` has succeeded (disk full, no permission, or a bug in the code that builds the entry), the balance has already been reduced but there is no ledger line, and the caller sees an error. This actually happened during the build: a wrong attribute name (`processor.name` instead of `proc_name`) charged two payments without recording them. Real systems prevent this with database **transactions** (all steps succeed, or none do).
- **Transaction IDs repeat across runs:** `txn_counter` starts at 0 every time the program starts, so a second run produces `wallet-W77-1` again, while the ledger file keeps entries from **every** run. Two processor objects with the same number also share ID sequences. A fix would be `uuid.uuid4()` or storing the counter in a file.