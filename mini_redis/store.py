"""Mini Redis 저장소 본체.

세 가지 자료구조를 조합한다.

    HashMap          키 -> Record(값, LRU 노드, 만료 시각)     "어디 있지?"를 O(1)로
    DoublyLinkedList 앞 = 최근에 쓴 키, 뒤 = 가장 오래 안 쓴 키   "누가 제일 오래됐지?"를 O(1)로
    MinHeap          (만료 시각, 키)                          "누가 제일 먼저 만료되지?"를 O(1)로

명령어 결과를 '파이썬 값'으로 돌려주고, Redis 스타일 글자로 바꾸는 일은 cli.py가 한다.
"""

import time

from mini_redis.doubly_linked_list import DoublyLinkedList
from mini_redis.hash_map import HashMap
from mini_redis.min_heap import MinHeap


class OutOfMemoryError(Exception):
    """키+값 하나가 maxmemory보다 커서 저장할 수 없을 때."""


class Record:
    """해시맵에 키마다 하나씩 저장하는 정보 묶음."""

    def __init__(self, value, lru_node, size):
        self.value = value
        self.lru_node = lru_node  # LRU 리스트 안의 내 노드 (바로 옮기거나 빼려고 기억)
        self.size = size          # len(utf8(key)) + len(utf8(value))
        self.expire_at = None     # 만료 시각(초). None이면 만료 없음


def entry_size(key, value):
    """used_memory 공식: 키와 값의 UTF-8 바이트 길이 합. 자료구조 오버헤드는 빼고 센다."""
    return len(key.encode("utf-8")) + len(value.encode("utf-8"))


class MiniRedis:
    """String 명령어 + LRU 자동 제거 + TTL 만료를 처리하는 저장소."""

    def __init__(self, clock=time.time):
        self._data = HashMap()           # 키 -> Record
        self._lru = DoublyLinkedList()   # 노드 data = 키
        self._ttl_heap = MinHeap()       # (expire_at, key)
        self._clock = clock              # 현재 시각 함수 (테스트에서 가짜 시계로 바꿀 수 있음)
        self.used_memory = 0
        self.maxmemory = 0               # 0 = 무제한
        self.evicted_keys = 0

    # ================= 내부: 삭제 / 만료 / 제거 =================

    def _delete(self, key):
        """키를 모든 구조에서 지운다.

        - 해시맵에서 Record 삭제 (Record 안의 expire_at, 즉 TTL 정보도 같이 사라짐)
        - LRU 리스트에서 노드 삭제 (노드를 기억하고 있어서 O(1))
        - used_memory 감소
        힙에 남은 (expire_at, key)는 바로 찾을 수 없으므로(O(n)) 그대로 두고,
        나중에 힙에서 꺼낼 때 '이미 없는 키'라서 버린다 (lazy deletion).
        """
        record = self._data.get(key)
        if record is None:
            return False
        self._data.remove(key)
        self._lru.remove_node(record.lru_node)
        self.used_memory -= record.size
        return True

    def _is_expired(self, record):
        return record.expire_at is not None and record.expire_at <= self._clock()

    def _remove_expired_keys(self):
        """힙 맨 위부터 '만료 시각이 지난 것'만 꺼내서 지운다.

        힙 맨 위가 가장 빠른 만료라서, 맨 위가 아직 안 지났으면
        나머지도 전부 안 지난 것이다 → 바로 멈춘다.
        꺼낸 항목의 시각이 Record의 현재 expire_at과 다르면
        (TTL이 바뀌었거나, 키가 지워졌거나, 덮어써진 경우) 낡은 항목이라 그냥 버린다.
        """
        now = self._clock()
        while self._ttl_heap.size() > 0 and self._ttl_heap.peek()[0] <= now:
            expire_at, key = self._ttl_heap.pop()
            record = self._data.get(key)
            if record is not None and record.expire_at == expire_at:
                self._delete(key)

    def _get_alive_record(self, key):
        """키 기반 명령어의 공통 첫 단계: 만료됐으면 지우고 '없는 키'(None)로 처리."""
        self._remove_expired_keys()
        record = self._data.get(key)
        if record is None:
            return None
        if self._is_expired(record):
            self._delete(key)
            return None
        return record

    def _evict_until_fit(self):
        """used_memory가 maxmemory 이하가 될 때까지 LRU 리스트 맨 뒤(가장 오래 안 쓴 키)부터 지운다."""
        while self.maxmemory > 0 and self.used_memory > self.maxmemory:
            oldest_key = self._lru.peek_back()
            if oldest_key is None:
                break
            self._delete(oldest_key)
            self.evicted_keys += 1

    # ================= String 명령어 =================

    def set(self, key, value):
        """SET: 저장하고 LRU 맨 앞으로. 덮어쓰면 TTL 초기화. 초과하면 LRU 제거."""
        size = entry_size(key, value)
        if self.maxmemory > 0 and size > self.maxmemory:
            raise OutOfMemoryError()

        record = self._get_alive_record(key)
        if record is not None:                          # 기존 키 덮어쓰기
            self.used_memory -= record.size
            record.value = value
            record.size = size
            record.expire_at = None                     # TTL 초기화 (힙 항목은 낡은 것이 됨)
            self._lru.move_to_front(record.lru_node)
        else:                                           # 새 키
            node = self._lru.insert_front(key)
            self._data.put(key, Record(value, node, size))
        self.used_memory += size

        self._evict_until_fit()

    def get(self, key):
        """GET: 만료 확인 → 없으면 None → 있으면 LRU 맨 앞으로 옮기고 값 반환."""
        record = self._get_alive_record(key)
        if record is None:
            return None                                  # 없거나 만료됨 → LRU 갱신 안 함
        self._lru.move_to_front(record.lru_node)         # 반환 성공 시에만 LRU 갱신
        return record.value

    def delete(self, key):
        """DEL: 지웠으면 1, 없으면 0."""
        if self._get_alive_record(key) is None:
            return 0
        self._delete(key)
        return 1

    def exists(self, key):
        """EXISTS: 있으면 1, 없으면 0. (LRU는 바꾸지 않음)"""
        return 1 if self._get_alive_record(key) is not None else 0

    def dbsize(self):
        """DBSIZE: 만료된 키를 먼저 치우고 남은 키 개수."""
        self._remove_expired_keys()
        return self._data.size()

    def keys(self):
        """KEYS: 만료된 키를 먼저 치우고 남은 키 목록."""
        self._remove_expired_keys()
        return self._data.keys()

    # ================= 메모리 명령어 =================

    def set_maxmemory(self, limit):
        """CONFIG SET maxmemory: 0 이상의 정수. 0은 무제한."""
        self.maxmemory = limit

    def info_memory(self):
        """INFO memory: (used_memory, maxmemory, evicted_keys)"""
        self._remove_expired_keys()
        return self.used_memory, self.maxmemory, self.evicted_keys

    # ================= TTL 명령어 =================

    def expire(self, key, seconds):
        """EXPIRE: 없으면 0. 0 이하면 즉시 삭제 후 1. 아니면 만료 시각을 기록하고 힙에 넣고 1."""
        record = self._get_alive_record(key)
        if record is None:
            return 0
        if seconds <= 0:
            self._delete(key)
            return 1
        record.expire_at = self._clock() + seconds
        self._ttl_heap.push((record.expire_at, key))
        return 1

    def ttl(self, key):
        """TTL: 없으면 -2, 만료 없음 -1, 있으면 남은 초(소수점 버림)."""
        record = self._get_alive_record(key)
        if record is None:
            return -2
        if record.expire_at is None:
            return -1
        return int(record.expire_at - self._clock())
