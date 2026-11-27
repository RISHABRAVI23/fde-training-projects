import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

# EXCEPTIONS


class PaymentError(Exception):
    """Base Exception for all Payment errors."""


class AmountError(PaymentError, ValueError):
    """Invalid amount."""


class BalanceError(PaymentError):
    """Balance file missing or corrupted."""


class PaymentDeclined(PaymentError):
    """Not enough balance or per transaction limit exceeded"""


class PaymentProcessor(Protocol):
    proc_name: str

    def charge(self, amount: int) -> tuple[str, int]: ...

    # def refund(self, txn_id:str) -> None:...


def give_txn_id(processor_type: str, processor_no: str, txn_counter: int) -> str:
    return f"{processor_type}-{processor_no}-{txn_counter}"


class BalanceStore:
    def __init__(self, balance_file_path: Path):
        self.balance_file_path = balance_file_path

    def read_balance(self) -> int:
        try:
            with open(self.balance_file_path, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            raise BalanceError(
                f"Cannot read Balance file at {self.balance_file_path}"
            ) from e

        try:
            balance = int(content)
        except ValueError as e:
            raise BalanceError(
                f"File at {self.balance_file_path} is corrupted. File content : {content!r}"
            ) from e

        if balance < 0:
            raise BalanceError(
                f"Negative balance found at {self.balance_file_path}. Balance = {balance}"
            )
        return balance

    def deduct(self, amount: int) -> int:
        balance = self.read_balance()
        if amount <= balance:
            with open(self.balance_file_path, encoding="utf-8", mode="w") as f:
                f.write(str(balance - amount))
            return balance - amount
        raise PaymentDeclined(
            f"Not enough Balance. Available balance = {balance}, tried to pay = {amount}."
        )


class WalletProcessor:
    def __init__(self, balance_store: BalanceStore, wallet_no: str):
        self.balance_store = balance_store
        self.txn_counter = 0
        self.processor_no = wallet_no
        self.proc_name = "wallet"

    def charge(self, amount: int) -> tuple[str, int]:
        self.balance_store.deduct(amount)
        self.txn_counter += 1
        return give_txn_id("wallet", self.processor_no, self.txn_counter), amount


class UPIProcessor:
    def __init__(self, balance_store: BalanceStore, UPI_no: str):
        self.balance_store = balance_store
        self.txn_counter = 0
        self.processor_no = UPI_no
        self.proc_name = "upi"

    def charge(self, amount: int) -> tuple[str, int]:
        if amount > 10000000:
            raise PaymentDeclined(
                f"Amount payable above per transaction limit. Amount = {amount}, Limit = {10000000}"
            )
        self.balance_store.deduct(amount)
        self.txn_counter += 1
        return give_txn_id("upi", self.processor_no, self.txn_counter), amount


class CardProcessor:
    def __init__(self, balance_store: BalanceStore, card_no: str):
        self.balance_store = balance_store
        self.txn_counter = 0
        self.processor_no = card_no
        self.proc_name = "card"

    def charge(self, amount: int) -> tuple[str, int]:
        fee = amount // 50  # 2%
        self.balance_store.deduct(fee + amount)
        self.txn_counter += 1
        return give_txn_id(
            "card", self.processor_no[-4:], self.txn_counter
        ), amount + fee


class Checkout:
    def __init__(self, processor: PaymentProcessor, ledger_path: Path):
        self.processor = processor
        self.ledger_path = ledger_path

    def pay(self, amount: int) -> str:
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise TypeError(
                f"Transaction amount must be integer. Given transaction amount = {amount!r} of type = {type(amount).__name__}"
            )

        if amount <= 0:
            raise AmountError(
                f"Transaction amount must be positive. Given transaction amount = {amount}"
            )

        txn_id, final_amount = self.processor.charge(amount)

        txn_data = {
            "time": datetime.now(UTC).isoformat(),
            "txn_id": txn_id,
            "processor": self.processor.proc_name,
            "amount": final_amount,
        }

        with open(self.ledger_path, mode="a", encoding="utf-8") as f:
            f.write(json.dumps(txn_data) + "\n")

        return txn_id
