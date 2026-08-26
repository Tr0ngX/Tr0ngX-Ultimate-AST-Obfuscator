import io

vals = [4, 2, 9]
state = {"i": 0}


def reader():
    i = state["i"]
    state["i"] += 1
    return vals[i] if i < len(vals) else -1


print(list(iter(reader, -1)))
print(state["i"])

bio = io.BytesIO(b"line1\nline2\nline3\n")
print([ln.strip() for ln in iter(bio.readline, b"")])
