from dataclasses import dataclass, field, InitVar, KW_ONLY


@dataclass
class Account:
    name: str
    password: InitVar[str]
    pw_len: int = field(init=False, default=0)
    roles: list = field(default_factory=lambda: ["user"])

    def __post_init__(self, password):
        self.pw_len = len(password)
        self.roles.append("auth:" + str(self.pw_len))


@dataclass
class Opts:
    name: str
    _: KW_ONLY
    retries: int = 3
    verbose: bool = False


a = Account("amy", "hunter2")
print(a.name, a.pw_len, a.roles)
b = Account("bo", "pw")
print(b.roles)
o = Opts("sync-job", retries=7)
print(o.name, o.retries, o.verbose)
try:
    Opts("bad", 9)
except TypeError:
    print("positional-after-kwonly rejected")
print(Account("carl", "x").pw_len)
