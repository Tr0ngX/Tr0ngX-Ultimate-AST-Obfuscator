def is_prime(n):
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


primes = [n for n in range(2, 200) if is_prime(n)]
print(len(primes), primes[:10], primes[-3:])
big = [2 ** 61 - 1, 2 ** 89 - 1, 67280421310721]
print([is_prime(x) for x in big])
composites = [561, 1105, 1729, 341550071728321]
print([is_prime(x) for x in composites])
