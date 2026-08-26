class Countdown:
    def __init__(self, start):
        self.cur = start

    def __iter__(self):
        return self

    def __next__(self):
        if self.cur <= 0:
            raise StopIteration
        v = self.cur
        self.cur -= 1
        return v


print(list(Countdown(5)))
c = Countdown(3)
print(next(c), next(c), next(c))
try:
    next(c)
except StopIteration:
    print("exhausted")
print(sum(Countdown(4)))
print(list(zip(Countdown(3), Countdown(9))))
