import sys


def fibonacci(limit):
    seq = []
    a, b = 0, 1
    while a < limit:
        seq.append(a)
        a, b = b, a + b
    return seq


def greet(name, rate=2.5):
    return f"hello {name}, rate={rate}"


class Box:
    def __init__(self, v):
        self.v = v

    def double(self):
        return self.v * 2


def main():
    print("hello Tr0ngX here")
    print(greet("world"))
    print("fib:", ",".join(str(x) for x in fibonacci(50)))
    box = Box(21)
    print("box:", box.double())
    try:
        n = int("42")
        print("n:", n)
    except ValueError:
        print("parse failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
