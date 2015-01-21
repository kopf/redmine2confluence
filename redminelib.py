import requests

from settings import REDMINE


def get(path):
    return requests.get(REDMINE['url'] + path, headers={'X-Redmine-API-Key': REDMINE['key']}).json()


def get_user(user_id):
    return get('/users/%s.json' % user_id)
