import os, datetime, shutil, stat
from typing import Callable, Optional, Iterable, List, Tuple

from scan_unused.utils import get_days_ago_str, size_getter_str, get_deleting_path

'''
Query the in-memory file structure multiple times to forcast what will get deleted / 
what is preventing something from getting deleted.
'''

class Node:
    '''
    Used to store file/folder metadata as tree structure.
    '''
    def __init__(self, name: str, is_folder: bool, owner: int, parent: 'Node'=None):
        self.name = name
        self.size = 0
        self.last_access = -1
        self.is_folder = is_folder
        self.children = [] if is_folder else None
        self.owner = owner
        self.parent = parent

    def get_path(self):
        full_list = []
        curr = self
        while curr is not None:
            full_list.append(curr.name)
            curr = curr.parent

        return os.path.join(*reversed(full_list))
    
    def get_size_str(self):
        return size_getter_str(self.size)
    
    def get_last_access_str(self):
        return f'{get_days_ago_str(self.last_access)} days ago'
    
    def __repr__(self):
        return f'{self.get_path()} ({get_days_ago_str(self.last_access)} days since access, {size_getter_str(self.size)})'

class Tree:
    def __init__(self, root: Node):
        self.root = root

    def from_dir(dir: str) -> 'Tree':
        '''
        Construct a tree given any directory.
        '''
        stats = os.stat(dir)
        if not stat.S_ISDIR(stats.st_mode):
            raise Exception('Must provide valid directory')
        root = Node(dir, True, stats.st_uid)

        # Unwrapped recursion for large FS
        stack = [root]
        while len(stack):
            parent = stack.pop()
            full = parent.get_path()
            try:
                for entry in os.scandir(full):
                    stats = entry.stat(follow_symlinks=False)
                    curr = Node(entry.name, entry.is_dir() and not entry.is_symlink(), stats.st_uid, parent)
                    if curr.is_folder: 
                        # Folders use mtime (but non-empty will get overwritten in recurse)
                        curr.last_access = stats.st_mtime 
                        stack.append(curr)
                    else:
                        # Files use atime
                        curr.last_access = stats.st_atime if not entry.is_symlink() else stats.st_mtime
                        curr.size = stats.st_size
                    parent.children.append(curr)
            except OSError:
                continue

        # Still need to recurse for sizes/access propagation
        def _recurse(node):
            if node.children:
                node.last_access = -1
                node.size = 0
                for c in node.children:
                    if c.children: _recurse(c)
                    node.size += c.size
                    node.last_access = max(node.last_access, c.last_access)
        _recurse(root)
        return Tree(root)
    
    def count_nodes(self):
        '''
        Count unwrapped tree nodes.
        '''
        def _recurse(node):
            count = 0
            for c in node.children:
                count += 1
                if c.is_folder: count += _recurse(c)
            return count
        return _recurse(self.root)

    def iter_nodes(self, satifies: Callable[[Node], bool]):
        '''
        Iterate unwrapped tree nodes when satisfies is true, skips sub-nodes.
        '''
        def _recurse(node):
            for c in node.children:
                if satifies(c): yield c
                elif c.is_folder: yield from _recurse(c)
        yield from _recurse(self.root)

    def iter_nodes_range(self, range: Tuple[Optional[float], Optional[float]], inverse: bool=False):
        '''
        Iterate nodes in a given (inclusive) timestamp range.
        '''
        yield from self.iter_nodes(lambda node: inverse ^ ((not range[0] or node.last_access >= range[0]) and (not range[1] or node.last_access <= range[1])))

    def iter_nodes_unused(self, days: int, future: int=None):
        '''
        Iterate nodes that have not been accessed in the given number of days. 
        Use future to see what files will be deleted on a given day ahead, assuming it is run every day.
        '''
        if future:
            # e.g. (3 days, 1 day in future) ->  in range [-3, -2]
            if future < days:
                from_t = (datetime.datetime.now() - datetime.timedelta(days=future+days-1))
                to_t = (datetime.datetime.now() - datetime.timedelta(days=future-1+days-1))
                yield from self.iter_nodes_range((from_t.timestamp(), to_t.timestamp()))
        else:
            # e.g. (3 days) -> in range [-infinity, -3]
            to_t = (datetime.datetime.now() - datetime.timedelta(days=days))
            yield from self.iter_nodes_range((None, to_t.timestamp()))

    @staticmethod
    def delete_nodes(nodes: Iterable[Node]):
        '''
        Delete list of nodes quickly.
        '''
        nodes = list(nodes)
        for node in nodes:
            full = node.get_path()
            path_tmp = get_deleting_path(full)
            os.rename(full, path_tmp)
        for node in nodes:
            full = node.get_path()
            path_tmp = get_deleting_path(full)
            shutil.rmtree(path_tmp) if node.is_folder else os.remove(path_tmp)
