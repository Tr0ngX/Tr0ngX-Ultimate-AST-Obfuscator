data = [3, 14, 15, 9, 26, 5, 35, 8, 97, 93]
big = [q := v // 10 for v in data if (sq := v * v) > 100]
print(big)
print([(v, sq) for v in data if (sq := v * v) > 500][:4])
it = iter(data)
even_squares = []
while (v := next(it, None)) is not None:
    if (sq := v * v) % 2 == 0:
        even_squares.append(sq)
print(even_squares)
text = "alpha beta gamma"
words = {w: n for w in text.split() if (n := len(w)) > 4}
print(words)
