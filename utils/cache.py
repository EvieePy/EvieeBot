"""The MIT License (MIT)

Copyright (c) 2018 EvieePy

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
import datetime
from collections import OrderedDict

import utils


class LRUNode:

    __slots__ = ('key', 'value', 'last_accessed')

    def __init__(self, key, value, last_accessed):
        self.key = key
        self.value = value
        self.last_accessed = last_accessed


class EvieeLRU:

    __slots__ = ('_limit', '_name', '_created', '_cache')

    def __init__(self, *, name, **kwargs):
        self._created = datetime.datetime.utcnow()
        self._limit = kwargs.get('limit', 100)
        self._name = name

        self._cache = OrderedDict()

    def __repr__(self):
        return f'<{self.__class__}, limit: {self._limit}, items: {self.size}, created: {self._created}>'

    def __str__(self):
        return f'{self._name}'

    def __getitem__(self, item):
        node = self._cache[item]
        node.last_accessed = datetime.datetime.utcnow()

        return node.value

    def __setitem__(self, key, value):
        if len(self._cache) >= self._limit:
            del self._cache[self.get_oldest().key]

        try:
            node = self._cache[key]
            node.last_accessed = datetime.datetime.utcnow()
            node.value = value
        except KeyError:
            node = LRUNode(key, value, datetime.datetime.utcnow())

        self._cache[key] = node

    def __delitem__(self, key):
        del self._cache[key]

    def __contains__(self, item):
        return item in self._cache

    def __len__(self):
        return len(self._cache)

    @property
    def size(self):
        return len(self._cache)

    @property
    def limit(self):
        return self._limit

    @limit.setter
    def limit(self, value: int):
        if value <= 2:
            raise utils.InvalidCacheLimit('Limit must be greater than 2.')
        self._limit = value

    @property
    def items(self):
        return self._cache.items()

    @property
    def values(self):
        return self._cache.values()

    @property
    def keys(self):
        return self._cache.keys()

    def get_oldest(self):
        return min(self._cache.values(), key=lambda _: _.last_accessed)

    def get(self, item, default=None):
        try:
            node = self._cache[item]
        except KeyError:
            return default

        node.last_accessed = datetime.datetime.utcnow()
        return node.value


class LFUNode:

    __slots__ = ('key', 'value', 'freqnode', 'previous', 'next')

    def __init__(self, key, value, freqnode, previous, next_):
        self.key = key
        self.value = value
        self.freqnode = freqnode

        self.previous = previous
        self.next = next_

    def free_myself(self):
        if self.freqnode.cache_head == self.freqnode.cache_tail:
            self.freqnode.cache_head = self.freqnode.cache_tail = None
        elif self.freqnode.cache_head == self:
            self.next.previous = None
            self.freqnode.cache_head = self.next
        elif self.freqnode.cache_tail == self:
            self.previous.next = None
            self.freqnode.cache_tail = self.previous
        else:
            self.previous.next = self.next
            self.next.previous = self.previous

        self.previous = None
        self.next = None
        self.freqnode = None


class FreqNode:

    __slots__ = ('freq', 'previous', 'next', 'cache_head', 'cache_tail')

    def __init__(self, freq, previous, next):
        self.freq = freq
        self.previous = previous
        self.next = next

        self.cache_head = None
        self.cache_tail = None

    def count_caches(self):
        if self.cache_head is None and self.cache_tail is None:
            return 0
        elif self.cache_head == self.cache_tail:
            return 1
        else:
            return '2+'

    def remove(self):
        if self.previous is not None:
            self.previous.next = self.next
        if self.next is not None:
            self.next.previous = self.previous

        previous = self.previous
        next_ = self.next
        self.previous = self.next = self.cache_head = self.cache_tail = None

        return previous, next_

    def pop_head_cache(self):
        if self.cache_head is None and self.cache_tail is None:
            return None
        elif self.cache_head == self.cache_tail:
            cache_head = self.cache_head
            self.cache_head = self.cache_tail = None
            return cache_head
        else:
            cache_head = self.cache_head
            self.cache_head.next.previous = None
            self.cache_head = self.cache_head.next
            return cache_head

    def append_cache_to_tail(self, cache_node):
        cache_node.freqnode = self

        if self.cache_head is None and self.cache_tail is None:
            self.cache_head = self.cache_tail = cache_node
        else:
            cache_node.previous = self.cache_tail
            cache_node.next = None
            self.cache_tail.next = cache_node
            self.cache_tail = cache_node

    def insert_after_me(self, freq_node):
        freq_node.previous = self
        freq_node.next = self.next

        if self.next is not None:
            self.next.previous = freq_node

        self.next = freq_node

    def insert_before_me(self, freq_node):
        if self.previous is not None:
            self.previous.next = freq_node

        freq_node.previous = self.previous
        freq_node.next = self
        self.previous = freq_node


class LFUCache(object):

    __slots__ = ('cache', 'limit', 'freq_link_head')

    def __init__(self, limit=1000):
        self.cache = {}
        self.limit = limit
        self.freq_link_head = None

    def __len__(self):
        return len(self.cache)

    def __str__(self):
        return f'LFU CACHE, LIMIT: {self.limit}, ENTRIES: {len(self)}'

    def __getitem__(self, item):
        return self.get(item)

    def __setitem__(self, key, value):
        return self.set(key=key, value=value)

    def get(self, key):
        if key in self.cache:
            cache_node = self.cache[key]
            freqnode = cache_node.freqnode
            value = cache_node.value

            self.move_forward(cache_node, freqnode)

            return value
        else:
            return -1

    def set(self, key, value):
        if self.limit <= 0:
            return -1

        if key not in self.cache:
            if len(self.cache) >= self.limit:
                self.dump_cache()

            self.create_cache(key, value)
        else:
            cache_node = self.cache[key]
            freq_node = cache_node.freq_node
            cache_node.value = value

            self.move_forward(cache_node, freq_node)

    def move_forward(self, cache_node, freqnode):
        if freqnode.next is None or freqnode.next.freq != freqnode.freq + 1:
            target_freq_node = FreqNode(freqnode.freq + 1, None, None)
            target_empty = True
        else:
            target_freq_node = freqnode.next
            target_empty = False

        cache_node.free_myself()
        target_freq_node.append_cache_to_tail(cache_node)

        if target_empty:
            freqnode.insert_after_me(target_freq_node)

        if freqnode.count_caches() == 0:
            if self.freq_link_head == freqnode:
                self.freq_link_head = target_freq_node

            freqnode.remove()

    def dump_cache(self):
        head_freq_node = self.freq_link_head
        self.cache.pop(head_freq_node.cache_head.key)
        head_freq_node.pop_head_cache()

        if head_freq_node.count_caches() == 0:
            self.freq_link_head = head_freq_node.nxt
            head_freq_node.remove()

    def create_cache(self, key, value):
        cache_node = LFUNode(key, value, None, None, None)
        self.cache[key] = cache_node

        if self.freq_link_head is None or self.freq_link_head.freq != 0:
            new_freq_node = FreqNode(0, None, None)
            new_freq_node.append_cache_to_tail(cache_node)

            if self.freq_link_head is not None:
                self.freq_link_head.insert_before_me(new_freq_node)

            self.freq_link_head = new_freq_node
        else:
            self.freq_link_head.append_cache_to_tail(cache_node)
