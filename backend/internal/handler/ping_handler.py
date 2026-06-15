from dataclasses import dataclass

from injector import inject

from pkg.response import success


@inject
@dataclass
class PingHandler:
    def ping(self):
        return success("pong")
