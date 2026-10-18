# 개념 정리

과제 목표 4가지를 **그림과 이 프로젝트의 실제 코드**로 설명합니다. 어려운 말은 처음 나올 때 풀어서 씁니다.

[← README](../README.md) · [평가 항목 정리](evaluation.md)

| 순서 | 개념 | 과제 목표 |
|---|---|---|
| 1 | [해시맵](#1-해시맵) | 해시 함수와 체이닝을 코드로 설명 |
| 2 | [이중 연결 리스트](#2-이중-연결-리스트) | O(1) 삽입/삭제/이동 |
| 3 | [LRU = 해시맵 + 이중 연결 리스트](#3-lru--해시맵--이중-연결-리스트) | O(1) LRU가 가능한 이유, 메모리 초과 시 제거 흐름 |
| 4 | [최소 힙](#4-최소-힙) | 힙이 TTL에 맞는 이유 |
| 5 | [TTL 만료 관리](#5-ttl-만료-관리) | 힙 + lazy deletion, GET 흐름 |
| 6 | [used_memory 공식](#6-used_memory-공식) | 메모리 계산 규칙 |

> **빅오(O) 표기 한 줄 정리**
> - **O(1)**: 데이터 양과 상관없이 거의 같은 시간 (사물함 번호를 알고 바로 열기)
> - **O(log n)**: 데이터가 2배가 되면 한 걸음 더 (100만 개여도 약 20걸음)
> - **O(n)**: 데이터 양만큼 (사물함을 처음부터 하나씩 열어 보기)

---

## 1. 해시맵

### 한 줄 설명

**키를 숫자로 바꿔서, 그 숫자로 "몇 번 칸"에 넣을지 바로 계산**하는 저장소입니다. 그래서 찾을 때도 처음부터 훑지 않고 그 칸으로 바로 갑니다.

| 용어 | 뜻 |
|---|---|
| 버킷(bucket) | 칸. 이 프로젝트에서는 길이가 정해진 배열 `[None] * capacity`의 한 칸 |
| 해시 함수 | 키(글자) → 숫자로 바꾸는 함수. 같은 키는 항상 같은 숫자 |
| 충돌 | 서로 다른 키가 같은 칸 번호를 받는 것 |
| 체이닝 | 충돌하면 그 칸에 리스트를 두고 줄줄이 이어 붙이는 방법 |
| 로드 팩터 | 키 개수 ÷ 칸 개수. 칸이 얼마나 붐비는지 |

### 해시 함수: 키 → 칸 번호

[`hash_map.py`의 `hash_string`](../mini_redis/hash_map.py#L36-L48)

```python
def hash_string(key):
    h = 0
    for byte in key.encode("utf-8"):         # ① 글자를 UTF-8 바이트로
        h = (h * 31 + byte) & 0xFFFFFFFF      # ② 31을 곱하고 더하기, ③ 32비트로 자르기
    return h

index = hash_string(key) % self._capacity     # ④ 칸 개수로 나눈 나머지 = 칸 번호
```

![해시 함수 과정](images/hash_function.svg)

| 단계 | 하는 일 | 왜 |
|---|---|---|
| ① UTF-8 바이트로 | `"user:1"` → `[117, 115, 101, 114, 58, 49]` | 한글 키(`이름`)도 숫자로 다룰 수 있게 |
| ② `h = h × 31 + 바이트` | 바이트를 하나씩 섞음 | 곱하기 때문에 **글자 순서**가 결과에 반영됨. `"ab"`=3105, `"ba"`=3135로 다름. 그냥 더하기만 하면 둘이 같아져서 충돌이 늘어남 |
| ③ `& 0xFFFFFFFF` | 32비트(0 ~ 약 43억) 안으로 자름 | 긴 키에서 숫자가 끝없이 커지지 않게 |
| ④ `% capacity` | 나머지 = 0 ~ capacity−1 | 배열 칸 번호로 바로 사용 |

31을 쓴 이유: 홀수인 소수라서 바이트가 고르게 섞이고, 자바의 `String.hashCode`도 같은 31을 씁니다.

### 체이닝: 같은 칸에 들어오면 이어 붙인다

칸이 8개일 때 `user:1`과 `user:9`는 해시값이 다르지만 **8로 나눈 나머지가 둘 다 2**입니다. 그래서 2번 칸에 둘 다 들어갑니다.

![체이닝](images/hash_chaining.svg)

| 칸 안의 구조로 무엇을 썼나 | 이유 |
|---|---|
| **이중 연결 리스트** (LRU에 쓰는 것과 같은 클래스) | 과제 권장. 이미 만든 것을 재사용. 가운데 항목을 지울 때 앞뒤만 이으면 됨 |
| 칸이 처음 쓰일 때 리스트를 만듦 (`None`이면 빈 칸) | 빈 칸까지 리스트를 미리 만들면 메모리 낭비 |
| 리스트에 넣는 항목 = `Entry(key, value)` | 같은 칸에 다른 키가 섞여 있으니, 찾을 때 **키를 비교**해야 함 |

```python
def _find_node(self, key):
    bucket = self._buckets[self._index(key)]     # 칸으로 바로 이동
    if bucket is None:
        return None
    for node in bucket.iter_nodes():             # 그 칸의 체인만 훑기
        if node.data.key == key:
            return node
    return None
```

### 로드 팩터 0.75 초과 → 칸 2배

[`HashMap.put`](../mini_redis/hash_map.py#L105-L113) → [`_resize`](../mini_redis/hash_map.py#L79-L93)

```python
def put(self, key, value):
    ...
    self._insert_new(key, value)
    if self._size / self._capacity > MAX_LOAD_FACTOR:   # 0.75
        self._resize()
```

![버킷 2배 확장](images/hash_resize.svg)

| 순서 | `_resize`가 하는 일 |
|---|---|
| 1 | 예전 버킷 배열을 따로 잡아 둔다 |
| 2 | `capacity`를 2배로 하고, 그 크기의 **새 빈 배열**을 만든다 |
| 3 | 예전 배열의 모든 칸, 모든 체인을 돌면서 항목을 **새 칸 번호로 다시 넣는다** (리해시) |

**왜 다시 넣어야 하나?** 칸 번호 = `해시값 % 칸 개수`라서, 칸 개수가 바뀌면 번호가 바뀝니다. `user:7`은 8칸일 때 0번이었지만 16칸에서는 8번입니다. 그대로 두면 `GET user:7`이 8번 칸을 보고 "없다"고 하게 됩니다.

**왜 0.75?** 너무 낮으면(예: 0.3) 빈 칸이 많아 메모리 낭비, 너무 높으면(예: 2.0) 체인이 길어져 찾기가 느려집니다. 0.75는 자바 `HashMap`도 쓰는 흔한 기준입니다.

---

## 2. 이중 연결 리스트

### 한 줄 설명

칸(노드)마다 **앞(prev)과 뒤(next)를 둘 다 기억**하는 리스트입니다. 노드 하나만 손에 쥐고 있으면, 앞뒤를 찾아 걸어갈 필요 없이 바로 떼거나 붙일 수 있습니다.

```python
class Node:
    def __init__(self, data=None):
        self.prev = None
        self.next = None
        self.data = data
```

### 가짜 노드(head, tail)

리스트 양 끝에 값이 없는 **가짜 노드**를 하나씩 둡니다. 그러면 "리스트가 비었나?", "맨 앞 노드인가?" 같은 예외 처리가 없어지고, 모든 연산이 **"어떤 노드 바로 뒤에 붙이기"**와 **"떼기"** 두 가지로 끝납니다.

![이중 연결 리스트](images/doubly_linked_list.svg)

| 메서드 | 내부에서 하는 일 | 바꾸는 연결선 |
|---|---|---|
| `insert_front(data)` | head 뒤에 붙이기 | 4개 |
| `insert_back(data)` | tail 앞 노드 뒤에 붙이기 | 4개 |
| `remove_front()` | head 다음 노드 떼기 | 2개 |
| `remove_back()` | tail 앞 노드 떼기 | 2개 |
| `remove_node(node)` | 그 노드 떼기 | 2개 |
| `move_to_front(node)` | 떼기 + head 뒤에 붙이기 | 2 + 4개 |

**모두 O(1)인 이유**: 반복문이 없고, 리스트 길이와 상관없이 바꾸는 연결선 개수가 항상 같기 때문입니다. 한쪽(next)만 있는 단일 연결 리스트라면, 노드를 뗄 때 "내 앞 노드"를 찾으러 처음부터 걸어가야 해서 O(n)이 됩니다.

```python
def _unlink(self, node):            # 떼기: 내 앞과 내 뒤를 서로 직접 연결
    node.prev.next = node.next
    node.next.prev = node.prev

def _link_after(self, prev_node, node):   # 붙이기: prev_node와 그 다음 사이에 끼우기
    next_node = prev_node.next
    node.prev = prev_node
    node.next = next_node
    prev_node.next = node
    next_node.prev = node
```

---

## 3. LRU = 해시맵 + 이중 연결 리스트

### LRU가 뭔가요?

**L**east **R**ecently **U**sed = "가장 오래전에 쓴 것". 메모리가 꽉 차면 **가장 오래 안 쓴 키부터 지우는** 규칙입니다. 최근에 쓴 데이터는 곧 또 쓸 가능성이 높다는 생각에서 나왔습니다.

### 왜 둘 다 필요한가

![LRU 구조](images/lru_structure.svg)

| 하는 일 | 담당 | 어떻게 O(1)? |
|---|---|---|
| ① 키로 Record 찾기 | 해시맵 | 칸 번호를 바로 계산 |
| ② 방금 쓴 키를 "최근"으로 | 리스트 | Record가 기억하는 `lru_node`를 `move_to_front` |
| ③ 가장 오래된 키 찾기 | 리스트 | 항상 **맨 뒤** (`tail.prev`) |
| ④ 그 키 지우기 | 둘 다 | 리스트는 `remove_node`, 해시맵은 `remove` |

- **해시맵만** 있으면: 찾기는 빠르지만 "누가 제일 오래됐나"를 알려면 전부 비교 → O(n)
- **리스트만** 있으면: 순서는 알지만 `user:1`의 노드를 찾으려고 처음부터 걸어가야 함 → O(n)
- **둘을 연결**(Record 안에 `lru_node`)하면: 해시로 노드를 바로 찾고(조회), 리스트에서 바로 옮김(갱신) → 둘 다 O(1)

### SET 한 번의 전체 흐름

[`MiniRedis.set`](../mini_redis/store.py#L109-L127) → [`_evict_until_fit`](../mini_redis/store.py#L98-L105)

![SET 흐름](images/set_flow.svg)

### 메모리 초과 시 제거: 과제 예시로 따라가기

![LRU 제거 과정](images/lru_eviction.svg)

```python
def _evict_until_fit(self):
    while self.maxmemory > 0 and self.used_memory > self.maxmemory:
        oldest_key = self._lru.peek_back()      # 리스트 맨 뒤 = 가장 오래 안 쓴 키
        self._delete(oldest_key)                # 해시맵, 리스트, used_memory에서 함께 제거
        self.evicted_keys += 1
```

**used_memory 갱신 지점은 딱 세 곳**입니다.

| 언제 | 갱신 |
|---|---|
| SET 새 키 | `+= size` |
| SET 덮어쓰기 | `-= 예전 size`, `+= 새 size` |
| 삭제 (DEL, 만료, LRU 제거 모두 `_delete` 하나를 거침) | `-= size` |

삭제 경로를 `_delete` 하나로 모았기 때문에, 어떤 이유로 지워지든 해시맵, 리스트, used_memory가 어긋나지 않습니다.

---

## 4. 최소 힙

### 한 줄 설명

**가장 작은 값이 항상 맨 위(0번)에 있도록** 유지하는 구조입니다. 전체가 정렬되어 있지는 않고, "부모 ≤ 자식"만 지킵니다. 그래서 정렬보다 싸게 유지할 수 있습니다.

![최소 힙](images/min_heap.svg)

| 연산 | 하는 일 | 시간 |
|---|---|---|
| `peek()` | 0번 보기 | O(1) |
| `push(item)` | 맨 끝에 넣고, 부모보다 작으면 자리를 바꾸며 올라감 (`_heapify_up`) | O(log n) |
| `pop()` | 0번을 꺼내고, 맨 끝 값을 0번에 놓은 뒤 더 작은 자식과 바꾸며 내려감 (`_heapify_down`) | O(log n) |

트리를 배열 하나에 저장하는 이유: 완전 이진 트리(왼쪽부터 빈틈없이 채운 트리)라서, 노드 i의 부모와 자식 위치를 **계산으로** 알 수 있습니다. 포인터가 필요 없습니다.

### 왜 TTL에 힙인가

TTL 관리에서 필요한 질문은 딱 하나입니다. **"지금 만료된 키가 있나?" = "가장 빠른 만료 시각이 지났나?"**

| 방법 | 가장 빠른 만료 찾기 | 새 만료 넣기 |
|---|---|---|
| 그냥 리스트 | O(n) 전부 비교 | O(1) |
| 항상 정렬된 리스트 | O(1) | O(n) 자리 찾아 끼우기 |
| **최소 힙** | **O(1)** | **O(log n)** |

힙의 항목은 `(expire_at, key)` 튜플입니다. 파이썬 튜플은 첫 번째 값부터 비교하므로 **만료 시각이 빠른 것**이 위로 올라갑니다.

---

## 5. TTL 만료 관리

### 만료 정보는 두 곳에

| 어디 | 무엇 | 역할 |
|---|---|---|
| `Record.expire_at` | 이 키의 **진짜** 만료 시각 (없으면 `None`) | 정답. TTL 명령, 만료 확인은 이것으로 |
| 힙 `(expire_at, key)` | 만료 **알림** 목록 | "언제 확인하러 가면 되는지" 빠르게 알려줌 |

### 힙 정리 + lazy deletion

[`MiniRedis._remove_expired_keys`](../mini_redis/store.py#L72-L85)는 **모든 명령어의 맨 처음**에 실행됩니다.

![TTL lazy deletion](images/ttl_lazy_deletion.svg)

**lazy deletion(게으른 삭제)이란?** 힙 가운데 있는 `(시각, a)`를 지금 지우려면 배열을 전부 뒤져야 합니다(O(n)). 그래서 지금은 그냥 두고, 나중에 맨 위로 올라와 꺼낼 때 **Record의 expire_at과 같은지** 비교해서 다르면 버립니다. 과제에서도 "lazy deletion 등은 구현 선택"이라고 허용합니다.

| 경우 | 꺼냈을 때 | 결과 |
|---|---|---|
| 정상 만료 | Record 있음, 시각 같음 | 키 삭제 |
| SET으로 덮어씀 | Record의 expire_at = None | 버림 (키는 살아 있음) |
| EXPIRE를 다시 걸어 시각이 바뀜 | 시각 다름 | 버림 (새 항목이 따로 있음) |
| DEL로 이미 지움 | Record 없음 | 버림 |
| DEL 후 같은 이름으로 새로 SET | 새 Record의 expire_at = None | 버림 (새 키는 안전) |

### GET 전체 흐름

[`MiniRedis.get`](../mini_redis/store.py#L129-L135)

![GET 흐름](images/get_flow.svg)

| 순서 | 코드 | 설명 |
|---|---|---|
| ① | `_remove_expired_keys()` | 힙 맨 위부터 시간이 지난 키들을 삭제 |
| ② | `self._data.get(key)` | 해시맵에서 Record 찾기. 없으면 `(nil)` |
| ③ | `_is_expired(record)` | 혹시 남아 있어도 만료 시각이 지났으면 삭제 후 `(nil)` (과제의 "키 기반 명령어는 먼저 만료 확인") |
| ④ | `move_to_front(record.lru_node)` | **값을 돌려줄 때만** LRU 갱신 |
| ⑤ | `return record.value` | `"value"` 출력 |

①과 ③은 `_get_alive_record` 한 함수에 들어 있고, GET, DEL, EXISTS, EXPIRE, TTL, SET이 모두 이 함수를 먼저 부릅니다.

---

## 6. used_memory 공식

```text
used_memory = Σ ( len(utf8(key)) + len(utf8(value)) )
```

| 예 | 키 바이트 | 값 바이트 | 합 |
|---|---|---|---|
| `SET user:1 "Alice"` | 6 | 5 | 11 |
| `SET 이름 홍길동` | 6 (한글 1자 = 3바이트) | 9 | 15 |
| `SET a ""` | 1 | 0 | 1 |

- 글자 수가 아니라 **바이트 수**입니다. `len("이름")`은 2지만 `len("이름".encode("utf-8"))`은 6입니다.
- 노드, 포인터, 버킷 같은 **자료구조 오버헤드는 세지 않습니다** (과제 규칙). 실제 파이썬 메모리와의 차이는 [평가 항목 4](evaluation.md#q3-used_memory에-오버헤드까지-포함하면)에 측정값과 함께 정리했습니다.
