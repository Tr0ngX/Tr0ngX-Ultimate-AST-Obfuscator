class Countdown:
    def __init__(self, n):
        self.n = n

    def __iter__(self):
        return CountdownIter(self.n)


class CountdownIter:
    def __init__(self, n):
        self.cur = n

    def __iter__(self):
        return self

    def __next__(self):
        if self.cur <= 0:
            raise StopIteration
        self.cur -= 1
        return self.cur + 1


print(list(Countdown(5)))
cd = Countdown(3)
it = iter(cd)
print(next(it), next(it), next(it))
try:
    next(it)
except StopIteration:
    print("exhausted")
print(list(iter(cd)))
print(iter(cd) is not iter(cd))
