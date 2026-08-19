with open('obf_mode3_clean.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's inspect the Kramer unhexlify and list conversions on 89MB
# content in Kramer is split by '/' and each char is hexlified
# Total characters in payload was 9.8MB, each char = 2 hex chars + 1 slash = ~29MB of string
# unhexlify(str(_n10_)) in a list comprehension of 10 million elements:
# ''.join(chr(ord(t)-key) for t in _n5_(_n1_)) -> 10 million loop iterations in Python
# ''.join(_n7_[...] for _n1_ in s1) -> another 10 million lookups with .index() in 36-char string (36 * 10M = 360M ops)
# and list(_n1_) -> creating a list of 10 million characters!
print('Analyzing complexity of 89MB Kramer decoding at startup...')
