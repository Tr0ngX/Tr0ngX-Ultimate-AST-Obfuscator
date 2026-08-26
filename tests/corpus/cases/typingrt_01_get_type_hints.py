import typing


def scale(factor: float, vec: list) -> dict:
    return {str(i): factor * v for i, v in enumerate(vec)}


hints = typing.get_type_hints(scale)
print(sorted(hints))
print(hints["factor"].__name__, hints["return"].__name__)


class Box:
    label: str
    size: int = 3

    def area(self) -> int:
        return self.size ** 2


hb = typing.get_type_hints(Box)
print(hb["label"].__name__, hb["size"].__name__)
print(Box.area.__annotations__["return"].__name__)
b = Box()
b.size = 4
print(b.area())
