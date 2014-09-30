import os
import pickle
import tempfile

def status_store_filename():
    return os.path.join(tempfile.gettempdir(), 'boundary-plugin-aws-elb-python-status')

def load_status_store():
    try:
        with open(status_store_filename(), 'rb') as f:
            return pickle.load(f)
    except:
        return None

def save_status_store(data):
    with open(status_store_filename(), 'wb') as f:
        return pickle.dump(data, f)

