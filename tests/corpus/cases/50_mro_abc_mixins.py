from abc import ABC, abstractmethod


class Storage(ABC):
    @abstractmethod
    def put(self, k, v): ...

    @abstractmethod
    def get(self, k, default=None): ...


class ListMixin:
    def items(self):
        return [(k, self.get(k)) for k in self.keys()]


class MemoryStorage(ListMixin, Storage):
    def __init__(self):
        self._d = {}

    def put(self, k, v):
        self._d[k] = v

    def get(self, k, default=None):
        return self._d.get(k, default)

    def keys(self):
        return sorted(self._d)


ms = MemoryStorage()
ms.put("b", 2)
ms.put("a", 1)
print(ms.items())
try:
    Storage()
except TypeError as e:
    print("abstract:", "abstract" in str(e))
print(issubclass(MemoryStorage, Storage), sorted(Storage.__abstractmethods__))
print(MemoryStorage.__mro__[1].__name__, MemoryStorage.__mro__[2].__name__)
