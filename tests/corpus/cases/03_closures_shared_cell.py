def account(balance):
    history = []

    def deposit(amount):
        nonlocal balance
        if amount <= 0:
            raise ValueError("bad amount")
        balance += amount
        history.append(("dep", amount))
        return balance

    def withdraw(amount):
        nonlocal balance
        balance -= amount
        history.append(("wd", amount))
        return balance

    def ledger():
        return list(history)

    def rebased(new_base):
        nonlocal balance, history
        delta = new_base - balance
        balance = new_base
        history = [("rebase", delta)]
        return delta

    return deposit, withdraw, ledger, rebased


dep, wd, led, reb = account(500)
dep(150)
wd(75)
print(dep(25), wd(200))
print(led())
print(reb(1000))
print(dep(1), led())
try:
    dep(-4)
except ValueError as e:
    print("rejected", e)
