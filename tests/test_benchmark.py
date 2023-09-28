import tempfile, os, random, contextlib, time

import pytest

from scan_unused.core import Node, Tree

'''
Use with pytest-memray
pytest --memray -k benchmark
'''

@contextlib.contextmanager
def build_synthetic(max_depth, max_children, max_nodes, in_memory=False):
    with tempfile.TemporaryDirectory() as temp_dir:
        count = 1
        stack = [temp_dir]
        node = Node(temp_dir, True, 0)

        # Uses a single stack to DFS a random file tree
        def _recurse():
            nonlocal count, node  
            path, depth = (os.path.sep.join(stack), len(stack))

            # Enforce depth limit, teminate with file
            if depth >= max_depth or (depth > max_depth/2 and random.random() >= 0.9):
                if count < max_nodes:
                    count += 1
                    if in_memory: 
                        assert node.name == stack[-1]
                        node.children.append(Node('file', False, 0, node))
                    else: 
                        open(os.path.join(path, 'file'), 'a').close()
            else:
                # Create random subfolders
                for child in range(random.randint(1, max_children-1)):
                    if count < max_nodes:
                        count += 1
                        path_append = f'really-long-name-{str(child)}'
                        if in_memory:
                            node.children.append(Node(path_append, True, 0, node))
                            node = node.children[-1]
                        else:
                            os.mkdir(os.path.join(path, path_append))
                        stack.append(path_append)
                        _recurse()
                        stack.pop()
                        if in_memory: node = node.parent
        _recurse()
        yield Tree(node) if in_memory else Tree.from_dir(temp_dir)

def test_benchmark_filesystem():
    # Test 1 million real files/folders - time-bounded
    MAX_NODES = int(1e6)
    with build_synthetic(max_depth=20, max_children=20, max_nodes=MAX_NODES, in_memory=False) as tree:
        assert tree.count_nodes() == MAX_NODES-1
        nodes = list(tree.iter_nodes(lambda _: random.random() > 0.90))
        tree.delete_nodes(nodes)

@pytest.mark.parametrize('_', range(100))
def test_benchmark_synthetic_small(_):
    # Test 1 thousand to ensure random file tree is reliable - memory-bounded
    MAX_NODES = int(1e3)
    with build_synthetic(max_depth=20, max_children=20, max_nodes=MAX_NODES, in_memory=True) as tree:
        assert tree.count_nodes() == MAX_NODES-1
        _ = list(tree.iter_nodes(lambda _: random.random() > 0.90))

def test_benchmark_synthetic_large():
    # Test 10 million virtual files/folders - memory-bounded
    MAX_NODES = int(1e7)
    with build_synthetic(max_depth=20, max_children=20, max_nodes=MAX_NODES, in_memory=True) as tree:
        assert tree.count_nodes() == MAX_NODES-1
        _ = list(tree.iter_nodes(lambda _: random.random() > 0.90))