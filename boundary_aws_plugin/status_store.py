import os
import pickle
import tempfile


def status_store_filename(basename):
    return os.path.join(tempfile.gettempdir(), basename)


def load_status_store(basename):
    try:
        with open(status_store_filename(basename), 'rb') as f:
            return pickle.load(f)
    except:
        return None


def save_status_store(basename, data):
    with open(status_store_filename(basename), 'wb') as f:
        return pickle.dump(data, f)

