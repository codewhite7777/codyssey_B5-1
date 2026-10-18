"""요구사항 확인용 테스트. 실행: python3 -m unittest -v

시간이 걸리는 TTL 테스트는 '가짜 시계'로 시간을 직접 움직여서 기다리지 않는다.
"""

import unittest

from mini_redis.cli import handle_line, parse_line
from mini_redis.doubly_linked_list import DoublyLinkedList
from mini_redis.hash_map import HashMap
from mini_redis.min_heap import MinHeap
from mini_redis.store import MiniRedis


class FakeClock:
    """테스트용 시계. advance(초)로 시간을 앞으로 보낸다."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def run_lines(db, lines):
    return [handle_line(db, line) for line in lines]


# ======================= 자료구조 =======================

class TestDoublyLinkedList(unittest.TestCase):
    def test_insert_remove_move(self):
        dll = DoublyLinkedList()
        a = dll.insert_back("A")
        dll.insert_back("B")
        dll.insert_front("C")
        self.assertEqual(list(dll), ["C", "A", "B"])

        dll.move_to_front(a)
        self.assertEqual(list(dll), ["A", "C", "B"])

        self.assertEqual(dll.remove_back(), "B")
        self.assertEqual(dll.remove_front(), "A")
        self.assertEqual(list(dll), ["C"])

    def test_remove_node_in_middle(self):
        dll = DoublyLinkedList()
        dll.insert_back("A")
        b = dll.insert_back("B")
        dll.insert_back("C")
        dll.remove_node(b)
        self.assertEqual(list(dll), ["A", "C"])
        self.assertEqual(len(dll), 2)

    def test_empty(self):
        dll = DoublyLinkedList()
        self.assertIsNone(dll.remove_front())
        self.assertIsNone(dll.remove_back())
        self.assertEqual(len(dll), 0)


class TestHashMap(unittest.TestCase):
    def test_put_get_remove(self):
        m = HashMap()
        m.put("a", 1)
        m.put("a", 2)  # 덮어쓰기
        self.assertEqual(m.get("a"), 2)
        self.assertTrue(m.contains("a"))
        self.assertEqual(m.size(), 1)
        self.assertTrue(m.remove("a"))
        self.assertFalse(m.remove("a"))
        self.assertIsNone(m.get("a"))

    def test_collision_chaining(self):
        # 칸 8개에서 "user:1"과 "user:9"는 같은 2번 칸에 들어간다 (README 그림과 같은 예)
        m = HashMap()
        m.put("user:1", "Alice")
        m.put("user:9", "Ivy")
        self.assertEqual(m._index("user:1"), m._index("user:9"))
        self.assertEqual(m.get("user:1"), "Alice")
        self.assertEqual(m.get("user:9"), "Ivy")
        m.remove("user:1")
        self.assertEqual(m.get("user:9"), "Ivy")

    def test_resize_when_load_factor_over_075(self):
        m = HashMap()
        for i in range(6):            # 6 / 8 = 0.75 → 아직 그대로
            m.put("k{}".format(i), i)
        self.assertEqual(m.capacity(), 8)
        m.put("k6", 6)                # 7 / 8 = 0.875 > 0.75 → 2배
        self.assertEqual(m.capacity(), 16)
        for i in range(7):
            self.assertEqual(m.get("k{}".format(i)), i)
        self.assertEqual(sorted(m.keys()), ["k{}".format(i) for i in range(7)])


class TestMinHeap(unittest.TestCase):
    def test_pop_in_order(self):
        h = MinHeap()
        for t in [30, 10, 50, 20, 40]:
            h.push((t, "key{}".format(t)))
        self.assertEqual(h.peek(), (10, "key10"))
        self.assertEqual([h.pop()[0] for _ in range(5)], [10, 20, 30, 40, 50])
        self.assertIsNone(h.pop())


# ======================= 명령어 =======================

class TestStringCommands(unittest.TestCase):
    def setUp(self):
        self.db = MiniRedis()

    def test_basic(self):
        out = run_lines(self.db, [
            'SET user:1 "Alice"', "GET user:1", "GET nope",
            "EXISTS user:1", "EXISTS nope", "DBSIZE",
            "DEL user:1", "DEL user:1", "DBSIZE", "KEYS",
        ])
        self.assertEqual(out, [
            "OK", '"Alice"', "(nil)",
            "(integer) 1", "(integer) 0", "(integer) 1",
            "(integer) 1", "(integer) 0", "(integer) 0", "(empty array)",
        ])

    def test_keys(self):
        run_lines(self.db, ["SET a 1", "SET b 2"])
        lines = handle_line(self.db, "KEYS").split("\n")   # 순서는 상관없음
        self.assertEqual(sorted(line.split(" ", 1)[1] for line in lines), ['"a"', '"b"'])

    def test_quoted_value_with_space(self):
        run_lines(self.db, ['SET msg "hello world"'])
        self.assertEqual(handle_line(self.db, "GET msg"), '"hello world"')
        self.assertEqual(parse_line('SET a ""'), ["SET", "a", ""])


class TestMemoryAndLRU(unittest.TestCase):
    def setUp(self):
        self.db = MiniRedis()

    def test_assignment_example(self):
        out = run_lines(self.db, [
            "CONFIG SET maxmemory 30",
            'SET user:1 "Alice"',   # 11
            'SET user:2 "Bob"',     # 9  -> 20
            'SET user:3 "Charlie"', # 13 -> 33 > 30 -> user:1 제거 -> 22
            "GET user:1",
            "INFO memory",
        ])
        self.assertEqual(out, [
            "OK", "OK", "OK", "OK", "(nil)",
            "used_memory:22\nmaxmemory:30\nevicted_keys:1",
        ])

    def test_get_refreshes_lru(self):
        run_lines(self.db, ["CONFIG SET maxmemory 30", "SET user:1 Alice", "SET user:2 Bob"])
        handle_line(self.db, "GET user:1")          # user:1을 최근으로 → 가장 오래된 건 user:2
        handle_line(self.db, "SET user:3 Charlie")
        self.assertEqual(handle_line(self.db, "EXISTS user:1"), "(integer) 1")
        self.assertEqual(handle_line(self.db, "EXISTS user:2"), "(integer) 0")

    def test_evict_several_keys(self):
        run_lines(self.db, ["CONFIG SET maxmemory 10", "SET a 1", "SET b 2", "SET c 3"])  # 각 2바이트
        handle_line(self.db, "SET big 1234567")       # 3 + 7 = 10 → 다른 키 모두 제거
        self.assertEqual(handle_line(self.db, "KEYS"), '1. "big"')
        self.assertEqual(self.db.evicted_keys, 3)
        self.assertEqual(self.db.used_memory, 10)

    def test_oom_single_entry_too_big(self):
        run_lines(self.db, ["CONFIG SET maxmemory 5", "SET a 1"])
        out = handle_line(self.db, "SET key toolong")
        self.assertEqual(out, "(error) OOM command not allowed when used_memory > 'maxmemory'")
        self.assertEqual(handle_line(self.db, "GET key"), "(nil)")
        self.assertEqual(handle_line(self.db, "GET a"), '"1"')  # 기존 데이터는 그대로

    def test_used_memory_utf8_and_overwrite(self):
        handle_line(self.db, "SET 이름 홍길동")      # 6 + 9 = 15 바이트
        self.assertEqual(self.db.used_memory, 15)
        handle_line(self.db, "SET 이름 a")           # 덮어쓰기: 6 + 1 = 7
        self.assertEqual(self.db.used_memory, 7)
        handle_line(self.db, "DEL 이름")
        self.assertEqual(self.db.used_memory, 0)

    def test_maxmemory_zero_is_unlimited(self):
        handle_line(self.db, "CONFIG SET maxmemory 0")
        for i in range(100):
            handle_line(self.db, "SET key{} value{}".format(i, i))
        self.assertEqual(handle_line(self.db, "DBSIZE"), "(integer) 100")
        self.assertEqual(self.db.evicted_keys, 0)


class TestTTL(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.db = MiniRedis(clock=self.clock)

    def test_assignment_example(self):
        run_lines(self.db, ["SET user:2 Bob"])
        self.assertEqual(handle_line(self.db, "EXPIRE user:2 3"), "(integer) 1")
        self.clock.advance(0.5)
        self.assertEqual(handle_line(self.db, "TTL user:2"), "(integer) 2")
        self.clock.advance(3)
        self.assertEqual(handle_line(self.db, "GET user:2"), "(nil)")
        self.assertEqual(handle_line(self.db, "TTL user:2"), "(integer) -2")

    def test_ttl_codes(self):
        handle_line(self.db, "SET a 1")
        self.assertEqual(handle_line(self.db, "TTL nope"), "(integer) -2")
        self.assertEqual(handle_line(self.db, "TTL a"), "(integer) -1")
        self.assertEqual(handle_line(self.db, "EXPIRE nope 10"), "(integer) 0")

    def test_expire_zero_or_negative_deletes(self):
        handle_line(self.db, "SET a 1")
        self.assertEqual(handle_line(self.db, "EXPIRE a 0"), "(integer) 1")
        self.assertEqual(handle_line(self.db, "EXISTS a"), "(integer) 0")

    def test_set_overwrite_clears_ttl(self):
        run_lines(self.db, ["SET a 1", "EXPIRE a 5", "SET a 2"])
        self.assertEqual(handle_line(self.db, "TTL a"), "(integer) -1")
        self.clock.advance(10)                       # 힙에 남은 낡은 항목이 a를 지우면 안 됨
        self.assertEqual(handle_line(self.db, "GET a"), '"2"')

    def test_expire_again_uses_new_time(self):
        run_lines(self.db, ["SET a 1", "EXPIRE a 5", "EXPIRE a 100"])
        self.clock.advance(10)
        self.assertEqual(handle_line(self.db, "EXISTS a"), "(integer) 1")

    def test_expired_keys_removed_everywhere(self):
        run_lines(self.db, ["SET a 1", "SET b 2", "EXPIRE a 1"])
        self.clock.advance(2)
        self.assertEqual(handle_line(self.db, "DBSIZE"), "(integer) 1")
        self.assertEqual(handle_line(self.db, "KEYS"), '1. "b"')
        self.assertEqual(self.db.used_memory, 2)
        self.assertEqual(len(self.db._lru), 1)

    def test_del_then_reset_key_not_affected_by_old_ttl(self):
        run_lines(self.db, ["SET a 1", "EXPIRE a 5", "DEL a", "SET a 2"])
        self.clock.advance(10)
        self.assertEqual(handle_line(self.db, "GET a"), '"2"')

    def test_expired_get_does_not_touch_lru(self):
        run_lines(self.db, ["SET a 1", "EXPIRE a 1"])
        self.clock.advance(2)
        self.assertEqual(handle_line(self.db, "GET a"), "(nil)")
        self.assertEqual(len(self.db._lru), 0)


class TestErrors(unittest.TestCase):
    def setUp(self):
        self.db = MiniRedis()

    def test_error_messages(self):
        out = run_lines(self.db, [
            "HELLO",
            "GET",
            "SET onlykey",
            "CONFIG SET maxmemory abc",
            "CONFIG SET maxmemory -1",
            "EXPIRE a notnumber",
            'SET a "unclosed',
        ])
        self.assertEqual(out, [
            "(error) ERR unknown command 'HELLO'",
            "(error) ERR wrong number of arguments for 'GET' command",
            "(error) ERR wrong number of arguments for 'SET' command",
            "(error) ERR value is not an integer or out of range",
            "(error) ERR value is not an integer or out of range",
            "(error) ERR value is not an integer or out of range",
            "(error) ERR unbalanced quotes in request",
        ])

    def test_lowercase_command_and_empty_line(self):
        self.assertEqual(handle_line(self.db, "set a 1"), "OK")
        self.assertIsNone(handle_line(self.db, "   "))


class TestConstraints(unittest.TestCase):
    def test_no_dict_set_collections(self):
        """mini_redis 코드에 dict, set, collections가 없는지 코드 구조(AST)로 검사한다."""
        import ast
        import os

        folder = os.path.join(os.path.dirname(__file__), "..", "mini_redis")
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                where = "{}:{}".format(name, getattr(node, "lineno", "?"))
                # {} {1, 2} {k: v} 같은 dict/set 문법
                self.assertNotIsInstance(node, (ast.Dict, ast.Set, ast.DictComp, ast.SetComp), where)
                # dict(...), set(...), frozenset(...) 호출
                if isinstance(node, ast.Name):
                    self.assertNotIn(node.id, ("dict", "set", "frozenset"), where)
                # import collections / from collections import ...
                if isinstance(node, ast.Import):
                    self.assertNotIn("collections", [a.name.split(".")[0] for a in node.names], where)
                if isinstance(node, ast.ImportFrom):
                    self.assertNotEqual((node.module or "").split(".")[0], "collections", where)


if __name__ == "__main__":
    unittest.main()
