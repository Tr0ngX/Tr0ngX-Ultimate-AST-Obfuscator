import math
import hashlib
import json

class MatrixCalculator:
    def __init__(self, size=3):
        self.size = size
        self.matrix = [[(i + 1) * (j + 1) for j in range(size)] for i in range(size)]

    def compute_stats(self):
        flattened = [val for row in self.matrix for val in row]
        total = sum(flattened)
        mean = total / len(flattened)
        variance = sum((x - mean) ** 2 for x in flattened) / len(flattened)
        std_dev = math.sqrt(variance)
        return {
            "sum": total,
            "mean": round(mean, 2),
            "std_dev": round(std_dev, 2)
        }

def fibonacci_generator(n):
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b

def hash_payload(data):
    raw = json.dumps(data, sort_keys=True)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def execute_complex_pipeline():
    print("=== [TEST 1: FIBONACCI] ===")
    fib_list = list(fibonacci_generator(10))
    print(f"Fibonacci (10): {fib_list}")

    print("\n=== [TEST 2: MATRIX CALCULATOR] ===")
    calc = MatrixCalculator(3)
    stats = calc.compute_stats()
    print(f"Matrix: {calc.matrix}")
    print(f"Matrix Stats: {stats}")

    print("\n=== [TEST 3: HASHING & LOGIC] ===")
    token = hash_payload({"fib": fib_list, "stats": stats})
    print(f"Computed SHA256 Signature: {token}")

    return token

if __name__ == "__main__":
    sig = execute_complex_pipeline()
    print("\n>>> Pipeline Completed Successfully! <<<")
