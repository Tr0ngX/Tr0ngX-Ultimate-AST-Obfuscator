from dataclasses import dataclass, field, InitVar


@dataclass
class Account:
    owner: str
    balance: float = 0.0
    bonus: InitVar[float] = 0.0
    log: list = field(default_factory=list, repr=False)
    flagged: bool = field(init=False, default=False)

    def __post_init__(self, bonus):
        if bonus:
            self.balance += bonus
            self.log.append(f"bonus:{bonus}")
        if self.balance >= 100:
            self.flagged = True


a = Account("ann", 90, bonus=20)
b = Account("bob")
a.log.append("deposit:5")
a.balance += 5
print(a)
print(b, b.flagged)
print(a.log is b.log, a.flagged)
