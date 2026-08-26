class X:
    pass


class Y:
    pass


class A(X, Y):
    pass


class B(Y, X):
    pass


ok = [[c.__name__ for c in A.__mro__]]
try:
    class Bad(A, B):
        pass
except TypeError as e:
    print("TypeError:", str(e)[:50])


class P(X, Y):
    pass


class Q:
    pass


class R(P, Q):
    pass


ok.append([c.__name__ for c in R.__mro__])
print(ok)
