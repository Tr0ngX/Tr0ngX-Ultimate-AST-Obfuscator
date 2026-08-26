def level1():
    total = 0

    def level2(delta):
        nonlocal total
        total += delta

        def level3():
            nonlocal total
            total *= 2
            return total

        return level3()

    return level2


h = level1()
print(h(3))
print(h(4))
print(h(-7))


def bank():
    balance = 100
    history = []

    def op(kind, amount):
        nonlocal balance
        if kind == "w":
            balance -= amount
        else:
            balance += amount
        history.append(balance)
        return balance

    return op


acct = bank()
out = [acct(k, a) for k, a in [("w", 30), ("d", 15), ("w", 5)]]
print(out)
