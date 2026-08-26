def load_all(names):
    errs = []
    for n in names:
        if not n:
            errs.append(ValueError("empty"))
        elif n.startswith("_"):
            errs.append(TypeError("private:" + n))
    if errs:
        raise BaseExceptionGroup("load", errs)
    return len(names)


try:
    try:
        load_all(["ok", "_priv"])
    except* TypeError as tg:
        print("type errs:", [str(e) for e in tg.exceptions])
        raise RuntimeError("aborting") from tg
except RuntimeError as err:
    print(type(err).__name__, type(err.__cause__).__name__, err.args[0])

print(load_all(["a", "b"]))
print("done")
