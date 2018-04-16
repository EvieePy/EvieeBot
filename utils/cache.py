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
