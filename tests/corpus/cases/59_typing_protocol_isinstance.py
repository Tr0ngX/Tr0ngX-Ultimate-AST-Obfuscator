from typing import Protocol, runtime_checkable


@runtime_checkable
class Closeable(Protocol):
    def close(self) -> None: ...


@runtime_checkable
class Readable(Protocol):
    def read(self, n: int = -1) -> bytes: ...


class FileLike:
    def close(self):
        pass

    def read(self, n=-1):
        return b"x"


class HalfOpen:
    def close(self):
        pass


f = FileLike()
print(isinstance(f, Closeable), isinstance(f, Readable))
print(isinstance(HalfOpen(), Closeable), isinstance(HalfOpen(), Readable))
print(isinstance(object(), Closeable))
print(issubclass(FileLike, Closeable))
print(Closeable._is_protocol)
