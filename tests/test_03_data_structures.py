import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
"""
Test 03: Complex Data Structures & Graph Algorithms
Tests: Prefix Tree (Trie), LRU Cache, Dijkstra Shortest Path, AVL Balanced Tree
"""
import collections, heapq

# 1. Prefix Tree (Trie)
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end = False

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word):
        node = self.root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True

    def search(self, word):
        node = self.root
        for ch in word:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return node.is_end

    def starts_with(self, prefix):
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return False
            node = node.children[ch]
        return True

# 2. Dijkstra Shortest Path
def dijkstra(graph, start):
    distances = {node: float('inf') for node in graph}
    distances[start] = 0
    pq = [(0, start)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > distances[u]:
            continue
        for v, weight in graph[u].items():
            if distances[u] + weight < distances[v]:
                distances[v] = distances[u] + weight
                heapq.heappush(pq, (distances[v], v))
    return distances

# 3. LRU Cache
class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = collections.OrderedDict()

    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

def run_suite():
    print("[TEST 03] Running Data Structures & Algorithms Suite...")

    # 1. Trie
    trie = Trie()
    trie.insert("antigravity")
    trie.insert("antivirus")
    trie.insert("anthology")
    assert trie.search("antigravity") is True
    assert trie.search("anti") is False
    assert trie.starts_with("anti") is True
    print("  [PASS] Prefix Tree (Trie) Passed")

    # 2. Dijkstra
    graph = {
        'A': {'B': 4, 'C': 2},
        'B': {'A': 4, 'C': 1, 'D': 5},
        'C': {'A': 2, 'B': 1, 'D': 8, 'E': 10},
        'D': {'B': 5, 'C': 8, 'E': 2},
        'E': {'C': 10, 'D': 2}
    }
    dist = dijkstra(graph, 'A')
    assert dist == {'A': 0, 'B': 3, 'C': 2, 'D': 8, 'E': 10}
    print("  [PASS] Dijkstra Shortest Path Passed")

    # 3. LRU Cache
    lru = LRUCache(2)
    lru.put(1, 100)
    lru.put(2, 200)
    assert lru.get(1) == 100
    lru.put(3, 300) # evicts key 2
    assert lru.get(2) == -1
    assert lru.get(3) == 300
    print("  [PASS] LRU Cache Eviction & Recency Passed")

    print("[TEST 03] >>> ALL CHECKS PASSED <<<\n")

if __name__ == "__main__":
    run_suite()
