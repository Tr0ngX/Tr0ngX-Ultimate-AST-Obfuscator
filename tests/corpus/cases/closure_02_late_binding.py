funcs = []
for i in range(3):
    funcs.append(lambda: i)

early = []
for j in range(3):
    early.append(lambda j=j: j * 10)

print([f() for f in funcs])
print([f() for f in early])


def outer():
    xs = []
    for k in range(3):
        def cap(k=k):
            return k ** 2
        xs.append(cap)
    return xs


print([g() for g in outer()])
