import os, datetime

def get_days_ago_str(last_access: float) -> int:
    '''
    Get how many days ago a given timestamp was.
    '''
    return (datetime.datetime.now() - datetime.datetime.fromtimestamp(last_access)).days if last_access and last_access >= 0 else -1

def size_getter_str(num: float, suffix: str="B") -> str :
    '''
    Convert bytes to human readable string.
    '''
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

def get_deleting_path(path: str):
    '''
    Consistent temporary intermedate used while removing a path.
    '''
    folders, basename = os.path.split(path)
    return os.path.join(folders, f'.deleting.{basename}')

def set_atime(path: str, atime: datetime.datetime=None, mtime: datetime.datetime=None):
    '''
    Set the access time of a given filename to the given atime.
    '''
    stats = None if (atime and mtime) else os.stat(path, follow_symlinks=False)
    os.utime(path, times=(atime.timestamp() if atime else stats.st_atime, mtime.timestamp() if mtime else stats.st_mtime), follow_symlinks=False)

def get_atime_day_offset(dir: str):
    '''
    Attempt to correct for innacurate or missing atime.
    '''
    dir = os.path.abspath(os.path.expanduser(dir))
    found_path_len = 0
    err = None
    if os.path.exists('/proc/mounts'):
        for m in open('/proc/mounts').readlines():
            fields = m.split(' ')
            path = fields[1]
            flags = fields[3]
            path_len = len(path)
            if path_len > found_path_len and (dir == path or dir.startswith(path + '/')):
                if 'relatime' in flags: 
                    found_path_len = path_len
                    err = None
                if 'noatime' in flags:
                    err = 'Directory is mounted with flag "noatime"'
    if err: 
        raise Exception(err)
    return 1 if found_path_len else 0
