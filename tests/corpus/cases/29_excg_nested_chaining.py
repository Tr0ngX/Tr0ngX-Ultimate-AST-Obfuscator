class AErr(Exception):
    pass


class BErr(Exception):
    pass


def level2():
    raise ExceptionGroup("level2", [BErr("b1"), BErr("b2")])


def level1():
    try:
        level2()
    except* BErr as eg:
        raise ExceptionGroup("level1-wrap", [AErr("a1"), *eg.exceptions]) from None


try:
    level1()
except ExceptionGroup as eg:
    flat = []

    def walk(group):
        for e in group.exceptions:
            if isinstance(e, ExceptionGroup):
                walk(e)
            else:
                flat.append(type(e).__name__ + ":" + str(e))

    walk(eg)
    print(eg.message)
    print(flat)

try:
    raise BaseExceptionGroup("mixed", [KeyboardInterrupt("k"), AErr("a")])
except* AErr as eg:
    print("a-part:", len(eg.exceptions))
except BaseExceptionGroup as eg:
    print("non-a residue:", [type(e).__name__ for e in eg.exceptions])
print("survived")
