from locust import HttpLocust, TaskSet, task

class UserBehavior(TaskSet):
    @task
    def get_keys(self):
        self.client.get('/api/keys')

class WebsiteUser(HttpLocust):
    host = 'http://localhost:8000'
    task_set = UserBehavior
    min_wait = 5000
    max_wait = 9000
