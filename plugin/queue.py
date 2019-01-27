import asyncio
from collections import deque


class Queue:

    def __init__(self):
        self.internal = deque()
        self.backwards = deque()

    @property
    def entries(self):
        return list(self.internal)

    @property
    def backwards_entries(self):
        return list(self.backwards)

    async def get(self):
        while True:
            try:
                item = self.internal.popleft()
            except IndexError:
                pass
            else:
                return item

            await asyncio.sleep(0.2)

    def put(self, item):
        self.internal.append(item)

    def put_left(self, item):
        self.internal.appendleft(item)

    def pop(self):
        return self.internal.popleft()

    def pop_index(self, index: int):
        return self.internal.pop(index)

    async def find_next(self):
        while True:
            try:
                item = self.internal.popleft()
            except IndexError:
                await asyncio.sleep(0.2)
                continue
            else:
                if item.is_dead:
                    await asyncio.sleep(0.2)
                    continue

            return item
