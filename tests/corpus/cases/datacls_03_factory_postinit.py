from dataclasses import dataclass, field


@dataclass
class Basket:
    items: list = field(default_factory=list)
    total: float = field(init=False, default=0.0)
    tag: str = "std"

    def __post_init__(self):
        self.total = float(sum(self.items))
        self.tag = self.tag.upper()


a = Basket([2, 3, 4])
b = Basket()
b.items.append(10)
print(a)
print(b.total, b.items, b.tag)
print(Basket(items=[]).total)
