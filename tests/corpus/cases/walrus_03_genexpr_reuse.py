import math

nums = (16, 25, -4, 36, 9)
roots = [r for n in nums if (r := math.isqrt(abs(n))) ** 2 == abs(n)]
print(roots)

scaled = [(r, r * 10) for n in nums if (r := abs(n) // 4) > 2]
print(scaled)


def consume(it):
    out = []
    while chunk := next(it, None):
        out.append(chunk * 2)
    return out


print(consume(iter([1, 0, 3, 5])))
