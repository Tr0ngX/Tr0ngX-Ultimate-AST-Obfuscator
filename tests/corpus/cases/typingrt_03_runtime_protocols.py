import typing


class Quacks(typing.Protocol):
    def quack(self) -> str: ...


Quacks = typing.runtime_checkable(Quacks)


class Duck:
    def quack(self) -> str:
        return "quack"


class Robot:
    def beep(self) -> str:
        return "beep"


print(isinstance(Duck(), Quacks), isinstance(Robot(), Quacks))


class Sized(typing.Protocol):
    def __len__(self) -> int: ...


Sized = typing.runtime_checkable(Sized)
print(isinstance([1, 2], Sized), isinstance(object(), Sized))
