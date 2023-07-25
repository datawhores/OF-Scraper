import collections
from multiprocessing import Pool
from multiprocessing.managers import BaseManager


class DequeManager(BaseManager):
    pass

class DequeProxy(object):
    def __init__(self, *args):
        self.deque = collections.deque(*args)
    def __len__(self):
        return self.deque.__len__()
    def put_left(self, x):
        self.deque.appendleft(x)
    def put(self, x):
        self.deque.append(x)
    def put_nowait(self, x):
        self.deque.append(x)
    def put_right(self, x):
        self.deque.append(x)  
    def get(self):
        return self.deque.pop()
    def get_rignt(self):
        return self.deque.pop()

    def get_left(self):
        return self.deque.popleft()

# Currently only exposes a subset of deque's methods.
DequeManager.register('DequeProxy', DequeProxy,
                      exposed=['__len__', 'put', 'put_left','put_right'
                               'get', 'get_right','get_left',"put_nowait"])


process_shared_deque = None  # Global only within each process.