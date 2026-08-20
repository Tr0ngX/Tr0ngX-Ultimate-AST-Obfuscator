import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import asyncio

def test_fstring_nesting():
    val = 42
    tag = 'CORE'
    s = f'PREFIX_{tag}_{val*2}_{len(f"{val}")}_SUFFIX'
    assert s == 'PREFIX_CORE_84_2_SUFFIX'

def test_walrus_operator():
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    filtered = [y for x in data if (y := x * 2) > 10]
    assert filtered == [12, 14, 16, 18, 20]
    assert (n := len(filtered)) == 5
    assert n == 5

def test_match_case_guards():
    def categorize(x):
        match x:
            case int(v) if v > 100:
                return 'LARGE_INT'
            case int(v) if v < 0:
                return 'NEG_INT'
            case (a, b) if a == b:
                return 'PAIR_EQUAL'
            case [first, *rest] if len(rest) == 2:
                return f'TRIO_{first}'
            case _:
                return 'DEFAULT'

    assert categorize(150) == 'LARGE_INT'
    assert categorize(-5) == 'NEG_INT'
    assert categorize((7, 7)) == 'PAIR_EQUAL'
    assert categorize([10, 20, 30]) == 'TRIO_10'
    assert categorize('abc') == 'DEFAULT'

async def test_async_context():
    class AsyncResource:
        async def __aenter__(self):
            return 'ACQUIRED'
        async def __aexit__(self, exc_type, exc, tb):
            return False

    async with AsyncResource() as res:
        assert res == 'ACQUIRED'

def run_suite():
    print('[TEST 05] Running Edge Cases and Syntax Matrix Test Suite...')
    test_fstring_nesting()
    print('  [PASS] Nested FS-Strings Passed')
    test_walrus_operator()
    print('  [PASS] Walrus Operator (:S) Passed')
    test_match_case_guards()
    print('  [PASS] Match Case Guards Passed')
    asyncio.run(test_async_context())
    print('  [PASS] Async Context Managers Passed')
    print('[TEST 05] ALL CHECKS PASSED\n')

if __name__ == '__main__':
    run_suite()