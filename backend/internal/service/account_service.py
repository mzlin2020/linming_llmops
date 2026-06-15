from dataclasses import dataclass
from typing import Optional

from injector import inject

from internal.exception import ValidateErrorException
from internal.extension.database_extension import db
from internal.model import Account
from pkg.password import hash_password, verify_password


@inject
@dataclass
class AccountService:
    def get_account(self, account_id) -> Optional[Account]:
        if account_id is None:
            return None
        try:
            return db.session.get(Account, int(account_id))
        except (TypeError, ValueError):
            return None

    def get_by_email(self, email: str) -> Optional[Account]:
        email = (email or "").strip().lower()
        if not email:
            return None
        return db.session.query(Account).filter(Account.email == email).first()

    def create_account(self, email: str, password: str, name: str = None) -> Account:
        email = (email or "").strip().lower()
        if self.get_by_email(email):
            raise ValidateErrorException("该邮箱已注册")
        account = Account(
            email=email,
            password_hash=hash_password(password),
            name=name or email.split("@")[0],
        )
        with db.auto_commit():
            db.session.add(account)
        return account

    def verify_credentials(self, email: str, password: str) -> Optional[Account]:
        account = self.get_by_email(email)
        if not account or not verify_password(password, account.password_hash):
            return None
        return account
