class Squares:
    limit = 5

    def __getitem__(self, i):
        if isinstance(i, slice):
            return [self[k] for k in range(*i.indices(self.limit))]
        if i >= self.limit:
            raise IndexError
        return i * i


sq = Squares()
print(list(sq))
print(list(iter(sq))[2])
print(max(sq))
print([x for x in sq if x % 2])
print(sq[1:4:2])
