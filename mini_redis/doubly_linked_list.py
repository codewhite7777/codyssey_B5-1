"""이중 연결 리스트 (Doubly Linked List).

양쪽 끝에 '가짜 노드(sentinel)' head, tail을 하나씩 둔다.

    head <-> [A] <-> [B] <-> [C] <-> tail
    (가짜)    앞                 뒤    (가짜)

가짜 노드가 있으면 "맨 앞인가? 비었나?" 같은 예외 처리가 사라지고,
모든 삽입/삭제/이동이 '연결선 몇 개 바꾸기'로 끝나서 O(1)이 된다.

이 리스트는 두 곳에서 재사용한다.
  1) LRU 순서 기록: 앞쪽 = 최근에 쓴 키, 뒤쪽 = 가장 오래 안 쓴 키
  2) 해시맵 버킷의 체인: 같은 칸에 들어온 항목들을 줄줄이 연결
"""


class Node:
    """리스트의 칸 하나. 앞(prev), 뒤(next), 담은 값(data)을 가진다."""

    def __init__(self, data=None):
        self.prev = None
        self.next = None
        self.data = data


class DoublyLinkedList:
    """가짜 head/tail 노드를 쓰는 이중 연결 리스트."""

    def __init__(self):
        self.head = Node()  # 맨 앞 가짜 노드 (값 없음)
        self.tail = Node()  # 맨 뒤 가짜 노드 (값 없음)
        self.head.next = self.tail
        self.tail.prev = self.head
        self._size = 0

    # ---------- 내부 도우미 ----------

    def _link_after(self, prev_node, node):
        """prev_node 바로 뒤에 node를 끼워 넣는다. 연결선 4개만 바꾼다. O(1)"""
        next_node = prev_node.next
        node.prev = prev_node
        node.next = next_node
        prev_node.next = node
        next_node.prev = node
        self._size += 1

    def _unlink(self, node):
        """node를 리스트에서 떼어 낸다. 양옆 노드끼리 직접 연결한다. O(1)"""
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = None
        node.next = None
        self._size -= 1

    # ---------- 과제 요구 메서드 ----------

    def insert_front(self, data):
        """맨 앞에 넣고, 만든 노드를 돌려준다. O(1)"""
        node = Node(data)
        self._link_after(self.head, node)
        return node

    def insert_back(self, data):
        """맨 뒤에 넣고, 만든 노드를 돌려준다. O(1)"""
        node = Node(data)
        self._link_after(self.tail.prev, node)
        return node

    def remove_front(self):
        """맨 앞 노드를 빼고 그 data를 돌려준다. 비어 있으면 None. O(1)"""
        if self._size == 0:
            return None
        node = self.head.next
        self._unlink(node)
        return node.data

    def remove_back(self):
        """맨 뒤 노드를 빼고 그 data를 돌려준다. 비어 있으면 None. O(1)"""
        if self._size == 0:
            return None
        node = self.tail.prev
        self._unlink(node)
        return node.data

    def remove_node(self, node):
        """이미 알고 있는 노드를 바로 뺀다. 찾을 필요가 없어서 O(1)"""
        self._unlink(node)
        return node.data

    def move_to_front(self, node):
        """노드를 떼어서 맨 앞에 다시 붙인다. O(1)"""
        if self.head.next is node:
            return
        self._unlink(node)
        self._link_after(self.head, node)

    # ---------- 편의 메서드 ----------

    def peek_back(self):
        """맨 뒤 노드의 data를 빼지 않고 본다. 비어 있으면 None. O(1)"""
        if self._size == 0:
            return None
        return self.tail.prev.data

    def __len__(self):
        return self._size

    def __iter__(self):
        """앞에서 뒤로 data를 하나씩 꺼낸다. (체인 탐색용, O(n))"""
        node = self.head.next
        while node is not self.tail:
            yield node.data
            node = node.next

    def iter_nodes(self):
        """앞에서 뒤로 노드 자체를 하나씩 꺼낸다. (체인에서 노드 삭제용)"""
        node = self.head.next
        while node is not self.tail:
            next_node = node.next
            yield node
            node = next_node
