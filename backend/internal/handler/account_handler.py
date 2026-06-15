from dataclasses import dataclass

from flask_login import current_user
from injector import inject

from internal.middleware import RequireLogin
from pkg.response import success


@inject
@dataclass
class AccountHandler:
    @RequireLogin
    def me(self):
        return success(current_user.to_dict())
