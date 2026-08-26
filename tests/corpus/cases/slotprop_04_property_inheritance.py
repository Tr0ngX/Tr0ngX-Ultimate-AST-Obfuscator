class Base:
    @property
    def level(self):
        return 0


class Mid(Base):
    @Base.level.getter
    def level(self):
        return super().level + 10


class Leaf(Mid):
    @Mid.level.setter
    def level(self, v):
        self._adj = v


L = Leaf()
print(L.level)
L.level = 5
print(L._adj, L.level)
print(isinstance(Base.level, property), isinstance(Mid.level, property))
