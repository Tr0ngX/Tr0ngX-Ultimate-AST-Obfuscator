class A:
    def who(self):
        return "A"


class B(A):
    def who(self):
        return "B>" + super().who()


class C(A):
    def who(self):
        return "C>" + super().who()


class D(B, C):
    def who(self):
        return "D>" + super().who()


class Mixin1:
    def who(self):
        return "m1"


class Mixin2:
    def who(self):
        return "m2"


class Feature(Mixin1, Mixin2):
    def who(self):
        return "feat>" + super().who()


print(D().who())
print(Feature().who())
print([c.__name__ for c in Feature.__mro__])
print(B.__mro__[-1].__name__, issubclass(D, A), isinstance(D(), A))
