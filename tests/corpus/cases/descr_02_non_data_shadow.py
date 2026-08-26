class LazySquare:
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if "_cached" not in obj.__dict__:
            obj.__dict__["_cached"] = obj.base ** 2
        return obj.__dict__["_cached"]


class Num:
    base = 7
    sq = LazySquare()


n = Num()
print(n.sq)
n.base = 9
print(n.sq)
del n.__dict__["_cached"]
print(n.sq)
