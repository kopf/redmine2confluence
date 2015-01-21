import json

import requests


class Confluence(object):
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.headers = {'Content-type': 'application/json'}

    def create_space(self, key, name, description):
        data = {
            'key': key, 'name': name,
            'description': {
                'plain': {
                    'value': description,
                    'representation': 'plain'
                }
            }
        }
        res = requests.post('{0}/space'.format(self.base_url),
                            auth=(self.username, self.password),
                            data=json.dumps(data),
                            headers=self.headers)
        return res.json()

    def create_page(self, title, body, space, username, display_name, parent_id=None):
        data = {
            "type": "page",
            "title": title,
            "space": {"key": space},
            "version": {
                "by": {
                    "type": "known",
                    "username": username,
                    "displayName": display_name
                }
            },
            "body": {
                "storage": {
                    "value": body,
                    "representation": "storage"
                }
            }
        }
        if parent_id is not None:
            data["ancestors"] = [{"type": "page", "id": parent_id}]
        res = requests.post('{0}/content'.format(self.base_url),
                            auth=(self.username, self.password),
                            data=json.dumps(data),
                            headers=self.headers)
        return res.json()
