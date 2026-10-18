"""해시맵 (체이닝 방식).

키를 숫자로 바꾸는 해시 함수로 "몇 번 칸(버킷)에 넣을지"를 바로 계산한다.
그래서 처음부터 끝까지 찾지 않아도 되고, 평균 O(1)로 넣고 찾는다.

    키 "user:1" ──해시 함수──> 3,458,935,874 ──% 칸 개수(8)──> 2번 칸

서로 다른 키가 같은 칸에 들어오면(충돌), 그 칸에 이중 연결 리스트를 두고
줄줄이 이어 붙인다. 이것이 체이닝이다.

    버킷 배열 (칸 8개)
    [0] 비어 있음
    [1] 비어 있음
    [2] ──> (user:1, Alice) <-> (user:9, Ivy)    ← 충돌한 두 항목
    [3] ──> (user:2, Bob)
    ...

항목 수 / 칸 개수(로드 팩터)가 0.75를 넘으면 칸을 2배로 늘리고
모든 항목을 새 칸 번호로 다시 넣는다(리해시). 체인이 길어지는 것을 막는다.
"""

from mini_redis.doubly_linked_list import DoublyLinkedList

INITIAL_CAPACITY = 8
MAX_LOAD_FACTOR = 0.75


class Entry:
    """버킷 체인에 들어가는 항목 하나. 키와 값을 묶는다."""

    def __init__(self, key, value):
        self.key = key
        self.value = value


def hash_string(key):
    """직접 설계한 해시 함수 (다항식 롤링 해시).

    1) 키(문자열)를 UTF-8 바이트로 바꾼다.   "ab" -> [97, 98]
    2) h = 0에서 시작해 바이트마다 h = h * 31 + 바이트
         "ab" -> (0*31 + 97) * 31 + 98 = 3105
       곱하기 31 덕분에 글자 '순서'가 결과에 반영된다. ("ab"와 "ba"가 달라짐)
    3) & 0xFFFFFFFF 로 32비트 안에 가둬서 숫자가 끝없이 커지지 않게 한다.
    """
    h = 0
    for byte in key.encode("utf-8"):
        h = (h * 31 + byte) & 0xFFFFFFFF
    return h


class HashMap:
    """체이닝 방식 해시맵. 버킷은 고정 길이 배열, 각 칸은 이중 연결 리스트."""

    def __init__(self, capacity=INITIAL_CAPACITY):
        self._capacity = capacity
        self._buckets = [None] * capacity  # 고정 길이 배열 (칸이 처음 쓰일 때 리스트를 만든다)
        self._size = 0

    # ---------- 내부 도우미 ----------

    def _index(self, key):
        """해시값을 칸 개수로 나눈 나머지 = 칸 번호 (0 ~ capacity-1)."""
        return hash_string(key) % self._capacity

    def _find_node(self, key):
        """키가 들어 있는 체인 노드를 찾는다. 없으면 None.

        칸 번호는 바로 계산하고, 그 칸의 체인만 훑는다.
        체인은 로드 팩터 덕분에 평균 1개 이하라서 평균 O(1).
        """
        bucket = self._buckets[self._index(key)]
        if bucket is None:
            return None
        for node in bucket.iter_nodes():
            if node.data.key == key:
                return node
        return None

    def _resize(self):
        """칸 개수를 2배로 늘리고 모든 항목을 새 칸 번호로 다시 넣는다.

        칸 개수가 바뀌면 '해시값 % 칸 개수'도 바뀌기 때문에
        기존 위치를 그대로 쓸 수 없고 하나씩 다시 계산해야 한다. O(n)
        """
        old_buckets = self._buckets
        self._capacity *= 2
        self._buckets = [None] * self._capacity
        self._size = 0
        for bucket in old_buckets:
            if bucket is None:
                continue
            for entry in bucket:
                self._insert_new(entry.key, entry.value)

    def _insert_new(self, key, value):
        """없는 키를 해당 칸의 체인 뒤에 붙인다."""
        index = self._index(key)
        if self._buckets[index] is None:
            self._buckets[index] = DoublyLinkedList()
        self._buckets[index].insert_back(Entry(key, value))
        self._size += 1

    # ---------- 과제 요구 메서드 ----------

    def put(self, key, value):
        """키가 있으면 값을 바꾸고, 없으면 새로 넣는다. 평균 O(1)"""
        node = self._find_node(key)
        if node is not None:
            node.data.value = value
            return
        self._insert_new(key, value)
        if self._size / self._capacity > MAX_LOAD_FACTOR:
            self._resize()

    def get(self, key):
        """키의 값을 돌려준다. 없으면 None. 평균 O(1)"""
        node = self._find_node(key)
        if node is None:
            return None
        return node.data.value

    def remove(self, key):
        """키를 지우고 True. 없으면 False. 평균 O(1)"""
        bucket = self._buckets[self._index(key)]
        if bucket is None:
            return False
        for node in bucket.iter_nodes():
            if node.data.key == key:
                bucket.remove_node(node)
                self._size -= 1
                return True
        return False

    def contains(self, key):
        """키가 있으면 True. 평균 O(1)"""
        return self._find_node(key) is not None

    def keys(self):
        """모든 키를 리스트로 돌려준다. 모든 칸을 훑으므로 O(n + 칸 개수)"""
        result = []
        for bucket in self._buckets:
            if bucket is None:
                continue
            for entry in bucket:
                result.append(entry.key)
        return result

    def size(self):
        """저장된 키 개수. O(1)"""
        return self._size

    def capacity(self):
        """현재 칸(버킷) 개수. 확장 확인용."""
        return self._capacity
