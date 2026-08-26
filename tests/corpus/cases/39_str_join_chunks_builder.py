from io import StringIO
import textwrap

parts = []
buf = StringIO()
for i in range(6):
    buf.write(f"row{i};")
    parts.append(f"[{i}]")
joined = "".join(parts)
csv_like = buf.getvalue().rstrip(";")
print(joined)
print(csv_like)
fragments = {"head": "Tr0ngX-", "mid": "CORPUS-", "tail": "seed"}
key = fragments["head"] + fragments["mid"] + fragments["tail"]
print(key)
wrapped = textwrap.fill(key, width=8)
print(wrapped.replace("\n", "|"))
print("-".join(reversed(key)))
print(sum(ord(ch) for ch in key))
print(key.split("-")[1].lower())
