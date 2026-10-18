r"""최소 힙 (Min Heap).

"가장 작은 값이 항상 맨 위(0번)에 있는" 완전 이진 트리를 배열로 저장한다.
TTL에서는 (만료 시각, 키)를 넣으므로, 맨 위 = 가장 먼저 만료될 키다.

    트리로 보면              배열로 보면
          (10)              [10, 20, 15, 40, 30]
         /    \               0   1   2   3   4
      (20)    (15)
      /  \                  i번의 부모 = (i - 1) // 2
    (40) (30)               i번의 자식 = 2i + 1, 2i + 2

- 가장 빠른 만료 보기(peek): 0번만 보면 됨 → O(1)
- 넣기(push) / 꺼내기(pop): 트리 높이만큼만 자리 바꿈 → O(log n)

튜플 (expire_at, key)는 첫 번째 값(expire_at)부터 비교되므로
만료 시각이 빠른 것이 위로 올라간다.
"""


class MinHeap:
    """배열 기반 최소 힙."""

    def __init__(self):
        self._items = []  # 인덱스로만 접근하는 배열 저장소

    def push(self, item):
        """맨 끝에 넣고 부모보다 작으면 위로 올린다. O(log n)"""
        self._items.append(item)
        self._heapify_up(len(self._items) - 1)

    def pop(self):
        """맨 위(가장 작은 값)를 꺼낸다. 비어 있으면 None. O(log n)

        1) 맨 위를 결과로 챙긴다.
        2) 맨 끝 값을 맨 위로 옮긴다.
        3) 자식보다 크면 아래로 내린다.
        """
        if not self._items:
            return None
        top = self._items[0]
        last = self._items.pop()
        if self._items:
            self._items[0] = last
            self._heapify_down(0)
        return top

    def peek(self):
        """맨 위(가장 작은 값)를 꺼내지 않고 본다. 비어 있으면 None. O(1)"""
        if not self._items:
            return None
        return self._items[0]

    def size(self):
        """들어 있는 항목 수."""
        return len(self._items)

    def _heapify_up(self, index):
        """index의 값이 부모보다 작은 동안 부모와 자리를 바꾸며 올라간다."""
        while index > 0:
            parent = (index - 1) // 2
            if self._items[index] < self._items[parent]:
                self._swap(index, parent)
                index = parent
            else:
                break

    def _heapify_down(self, index):
        """index의 값이 자식보다 큰 동안 더 작은 자식과 자리를 바꾸며 내려간다."""
        count = len(self._items)
        while True:
            left = 2 * index + 1
            right = 2 * index + 2
            smallest = index
            if left < count and self._items[left] < self._items[smallest]:
                smallest = left
            if right < count and self._items[right] < self._items[smallest]:
                smallest = right
            if smallest == index:
                break
            self._swap(index, smallest)
            index = smallest

    def _swap(self, i, j):
        self._items[i], self._items[j] = self._items[j], self._items[i]
