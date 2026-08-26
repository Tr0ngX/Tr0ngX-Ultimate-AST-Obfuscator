class A:
    def who(self):
        return "A"


class B(A):
    def who(self):
        return "B->" + super().who()


class C(A):
    def who(self):
        return "C->" + super().who()


class D(B, C):
    def who(self):
        return "D->" + super().who()


d = D()
print(d.who())
print([c.__name__ for c in D.__mro__])
print(D.__mro__[1:] == tuple(D.mro())[1:])
