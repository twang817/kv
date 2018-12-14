import random
import string
import time

from locust import Locust, TaskSet, events, task
from pymemcache.client.base import Client


class MemcacheClient(object):
    def __init__(self, host, port):
        self.client = Client((host, port))

    def __getattr__(self, name):
        func = getattr(self.client, name)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                total_time = int((time.time() - start_time) * 1000)
                events.request_failure.fire(request_type='memcache', name=name, response_time=total_time, exception=e)
                raise
            else:
                total_time = int((time.time() - start_time) * 1000)
                events.request_success.fire(request_type='memcache', name=name, response_time=total_time, response_length=0)
            return result
        return wrapper

class MemcacheLocust(Locust):
    def __init__(self, *args, **kwargs):
        self.client = MemcacheClient(self.host, self.port)
        super().__init__(*args, **kwargs)

class UserBehavior(TaskSet):
    @task
    def set_key(self):
        k = random.randint(5, 15)
        key = ''.join(random.choices(string.ascii_letters + string.digits, k=k))
        value = '%s-%s' % (key, 1)
        result = self.client.set(key, value)
        assert result

class User(MemcacheLocust):
    host = 'localhost'
    port = 11211
    task_set = UserBehavior
    min_wait = 5000
    max_wait = 9000
