class Base:
    def __init__(self, tag="none", **kw):
        print(f"Base.init:{tag}")
        super().__init__(**kw)


class Left(Base):
    def __init__(self, **kw):
        print("Left.init")
        super().__init__(**kw)


class Right(Base):
    def __init__(self, **kw):
        print("Right.init")
        super().__init__(**kw)


class Child(Left, Right):
    def __init__(self, **kw):
        print("Child.init")
        super().__init__(**kw)


Child(tag="T")
print([c.__name__ for c in Child.__mro__])
print(Left.__mro__[1].__name__, Right.__mro__[2].__name__)


class A:
    pass


class B(A):
    pass


class C(A):
    pass


class D(B, C):
    pass


print([c.__name__ for c in D.__mro__])
try:
    class Bad(B, B):
        pass
except TypeError:
    print("dup-base-rejected")
