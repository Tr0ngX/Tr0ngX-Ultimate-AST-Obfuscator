words = "the cat and the hat sat on the mat with a rat".split()
groups = {}
for w in words:
    groups.setdefault(len(w), []).append(w)
print({k: v for k, v in sorted(groups.items())})
by_first = {}
for w in words:
    by_first.setdefault(w[0], []).append(w)
print({k: len(v) for k, v in by_first.items()})
freq = {w: words.count(w) for w in set(words)}
print(sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:5])
length_index = {w: i for i, w in enumerate(words)}
print(length_index["hat"], length_index.get("dog", -1))
