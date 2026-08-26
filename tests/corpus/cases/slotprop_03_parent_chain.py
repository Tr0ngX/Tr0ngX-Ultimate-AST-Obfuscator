class Node:
    __slots__ = ("value", "_parent")

    def __init__(self, value):
        self.value = value
        self._parent = None

    @property
    def parent(self):
        return self._parent

    def attach(self, other):
        other._parent = self


root, kid, grand = Node("r"), Node("k"), Node("g")
kid.attach(root)
grand.attach(kid)
chain = []
cur = grand
while cur.parent:
    chain.append(cur.value)
    cur = cur.parent
chain.append(cur.value)
print("->".join(chain))
print(Node.__slots__)
print(hasattr(root, "__dict__"))
