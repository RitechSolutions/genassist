import os



def get_root_directory_path():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))