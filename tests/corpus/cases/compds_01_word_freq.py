text = "the quick brown fox jumps over the lazy dog the end"
freq = {}
for w in text.split():
    freq[w] = freq.get(w, 0) + 1
top = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
print(top)
wc = {w: len(w) for w in sorted(set(text.split()))}
print(wc)
uniq_first = {v: k for k, v in wc.items()}
print(sorted(uniq_first.items()))
