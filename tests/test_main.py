import pytest, tempfile, datetime, os

from scan_unused.core import Node, Tree
from scan_unused.utils import set_atime, get_days_ago_str

@pytest.fixture
def _test_dir_fixture(request):
    files = request.param
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write dummy files
        for path, days in files:
            folders, _ = os.path.split(path)
            f_time = (datetime.datetime.now() - datetime.timedelta(days=days))
            if folders: 
                os.makedirs(os.path.join(temp_dir, folders), exist_ok=True)
            if path.endswith('/'):
                set_atime(file_path, None, f_time)
            else:
                file_path = os.path.join(temp_dir, path)
                with open(file_path, 'wb') as f:
                    f.write(f'This test file was last accessed {days} days ago'.encode())
                set_atime(file_path, f_time, None)
        yield temp_dir

@pytest.mark.parametrize("_test_dir_fixture", [[('subfolder/1.txt', 2.9), ('2.txt.gz', 3.1)]], indirect=True)
def test_create(_test_dir_fixture):
    three_days_ago = (datetime.datetime.now() - datetime.timedelta(days=3)).timestamp()
    assert os.path.exists(os.path.join(_test_dir_fixture, 'subfolder/1.txt'))
    assert os.path.exists(os.path.join(_test_dir_fixture, '2.txt.gz'))
    assert os.stat(os.path.join(_test_dir_fixture, 'subfolder/1.txt')).st_atime > three_days_ago
    assert os.stat(os.path.join(_test_dir_fixture, '2.txt.gz')).st_atime < three_days_ago

@pytest.mark.parametrize("_test_dir_fixture", [[('subfolder/1.txt', 2.9), ('2.txt.gz', 3.1)]], indirect=True)
def test_tree(_test_dir_fixture):
    tree = Tree.from_dir(_test_dir_fixture)
    assert tree.count_nodes() == 3
    assert len(tree.root.children) == 2
    assert tree.root.owner == os.getuid()
    assert tree.root.is_folder == True
    
    tree.root.children.sort(key=lambda x: x.name, reverse=True)
    assert tree.root.children[0].get_path() == os.path.join(_test_dir_fixture, 'subfolder')
    assert tree.root.children[0].children[0].get_path() == os.path.join(_test_dir_fixture, 'subfolder', '1.txt')
    assert tree.root.children[1].get_path() == os.path.join(_test_dir_fixture, '2.txt.gz')

    assert get_days_ago_str(tree.root.children[0].last_access) == 2
    assert get_days_ago_str(tree.root.children[0].children[0].last_access) == 2
    assert get_days_ago_str(tree.root.children[1].last_access) == 3

@pytest.mark.parametrize("_test_dir_fixture", [[('subfolder/1.txt', 3.1), ('2.txt.gz', 2.9)]], indirect=True)
def test_unused(_test_dir_fixture):
    tree = Tree.from_dir(_test_dir_fixture)
    assert tree.count_nodes() == 3
    nodes = list(tree.iter_nodes_unused(3))
    assert len(nodes) == 1
    assert nodes[0].get_path() == os.path.join(_test_dir_fixture, 'subfolder')
    assert len(nodes[0].children) == 1

    assert os.path.exists(os.path.join(_test_dir_fixture, '2.txt.gz'))
    assert os.path.exists(nodes[0].get_path())
    tree.delete_nodes(nodes)
    assert os.path.exists(os.path.join(_test_dir_fixture, '2.txt.gz'))
    assert not os.path.exists(nodes[0].get_path())

@pytest.mark.parametrize("_test_dir_fixture", [[('subfolder/1.txt', 2.9), ('2.txt.gz', 3.1)]], indirect=True)
def test_future(_test_dir_fixture):
    tree = Tree.from_dir(_test_dir_fixture)
    assert tree.count_nodes() == 3
    nodes = list(tree.iter_nodes_unused(3, 1))
    assert len(nodes) == 1
    assert nodes[0].get_path() == os.path.join(_test_dir_fixture, 'subfolder')
    assert len(nodes[0].children) == 1

    # There should not be files with atimes in the future
    assert len(list(tree.iter_nodes_unused(3, 3))) == 0

@pytest.mark.parametrize("_test_dir_fixture", [[('.hidden_folder/1.txt', 0), ('.hidden_file.txt', 0)]], indirect=True)
def test_hidden(_test_dir_fixture):
    tree = Tree.from_dir(_test_dir_fixture)
    assert len(tree.root.children) == 2
    tree.root.children.sort(key=lambda x: x.name, reverse=True)
    assert tree.root.children[0].get_path() == os.path.join(_test_dir_fixture, '.hidden_folder')
    assert tree.root.children[1].get_path() == os.path.join(_test_dir_fixture, '.hidden_file.txt')

@pytest.mark.parametrize("_test_dir_fixture", [[('subfolder/1.txt', 2.9), ('2.txt.gz', 3.1)]], indirect=True)
def test_symlink(_test_dir_fixture):

    harmless_symlink = os.path.join(_test_dir_fixture, 'harmless_link')
    long_time_ago = (datetime.datetime.now() - datetime.timedelta(days=5))
    os.symlink(_test_dir_fixture, harmless_symlink)
    set_atime(harmless_symlink, long_time_ago, long_time_ago)

    tree = Tree.from_dir(_test_dir_fixture)
    assert tree.count_nodes() == 4
    nodes = list(tree.iter_nodes_unused(3))
    tree.delete_nodes(nodes)

    assert os.path.exists(_test_dir_fixture)
    assert not os.path.exists(harmless_symlink)