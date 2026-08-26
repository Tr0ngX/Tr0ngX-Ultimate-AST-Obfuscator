stream = iter("the quick brown fox jumps".split())
chunks = []
while (batch := [w for _, w in zip(range(2), stream)]):
    chunks.append("-".join(batch))
print(chunks)
stack = [5, 3, 8, 1]
drained = []
while stack and (top := stack.pop()):
    drained.append(top * top)
print(drained)
lines = ["a=1", "b=2", "# comment", "c=3"]
config = {}
for line in lines:
    if "#" in line:
        continue
    k, _, v = line.partition("=")
    config[k] = int(v)
if (n := config.get("b")) and n == 2:
    config["b"] = n * 10
print(config)
