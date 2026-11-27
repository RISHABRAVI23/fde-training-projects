import os
from contextlib import contextmanager
from pathlib import Path


# Method 1
class TemporaryDirectoryChange:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.current_dir = os.getcwd()
        os.chdir(self.path)
        # print("entered")
        return self

    def __exit__(self, exc_type, exc, tb):
        os.chdir(self.current_dir)
        # print("exit")
        return False


# Method 2
@contextmanager
def temporary_directory_change(path):
    current_dir = os.getcwd()

    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(current_dir)


if __name__ == "__main__":
    with TemporaryDirectoryChange(Path(__file__).parent.parent.parent / "day-1"):
        print(os.getcwd())

    print(os.getcwd())

    with temporary_directory_change(Path(__file__).parent.parent.parent / "day-1"):
        print(os.getcwd())

    print(os.getcwd())
