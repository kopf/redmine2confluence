import json
import xmlrpclib
import time
import urllib

import logbook
import requests

log = logbook.Logger('confluence')

class InvalidXML(Exception):
    pass


class Timeout(Exception):
    pass


class Confluence(object):
    def __init__(self, base_url, username, password, verify_ssl=True):
        self.base_url = base_url + '/rest/api'
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        if not verify_ssl:
            requests.packages.urllib3.disable_warnings()
        self.headers = {'Content-type': 'application/json'}
        self.server = xmlrpclib.ServerProxy('%s/rpc/xmlrpc' % base_url)
        self.token = self.server.confluence2.login(self.username, self.password)

    def _post(self, url, data, files=None, headers=None, jsonify=True, retry=5):
        if not retry:
            raise RuntimeError('Number of retries exceeded! Aborting.')
        if headers is None:
            headers = self.headers
        if jsonify:
            data = json.dumps(data)
        try:
            res = requests.post(url, auth=(self.username, self.password),
                                data=data, headers=headers, files=files,
                                verify=self.verify_ssl)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            log.warn('Exception occurred making request: {0}. Retrying...'.format(e))
            time.sleep(1)
            return self._post(url, data, files=files, headers=headers,
                              jsonify=jsonify, retry=retry-1)
        if not 200 <= res.status_code < 300:
            try:
                error = json.loads(res.text)
            except ValueError:
                raise RuntimeError('Could not parse json: %s' % res.text)
            if error['message'] == 'Error parsing xhtml':
                raise InvalidXML(error['message'])
            elif 'Read timed out' in error['message']:
                log.warn('Timed out. Retrying...')
                time.sleep(1)
                return self._post(url, data, files=files, headers=headers,
                                  jsonify=jsonify, retry=retry-1)
            elif 'same file name as an existing attachment' in error['message']:
                # Append an underscore to the filename, before extension
                files['file'] = (files['file'][0].replace('.', '_.'), files['file'][1])
                return self._post(url, data, files=files, headers=headers,
                                  jsonify=jsonify, retry=retry)
            raise RuntimeError(res.text)
        return res.json()

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
        try:
            self._post('{0}/space'.format(self.base_url), data)
        except RuntimeError as e:
            # space already exists
            log.warn('Space {0} already exists, skipping creation'.format(key))

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
        return self._post('{0}/content'.format(self.base_url), data)

    def add_attachment(self, confluence_id, filename, data, description):
        filename = urllib.quote_plus(filename.encode('utf8'))
        url = '{0}/content/{1}/child/attachment'.format(
            self.base_url, confluence_id)
        return self._post(url, {'comment': description},
                          files={'file': (filename, data)},
                          headers={'X-Atlassian-Token': 'nocheck'},
                          jsonify=False)

    def move_page(self, page_id, target_page_id):
        self.server.confluence2.movePage(
            self.token, str(page_id), str(target_page_id), 'append')

    def get_page(self, page_id):
        url = '{0}/content/{1}?expand=body.view,version'.format(
            self.base_url, page_id)
        return requests.get(
            url, auth=(self.username, self.password), headers=self.headers,
            verify=self.verify_ssl).json()

    def update_page(self, page_id, content):
        current_page = self.get_page(page_id)
        ver_number = current_page['version']['number'] + 1
        title = current_page['title']
        data = {
            "id": page_id,
            "type": "page",
            "title": title,
            "body":{
                "storage":{
                    "value": content,
                    "representation": "storage"
                }
            },
            "version":{
                "number": ver_number
            }
        }
        return requests.put('{0}/content/{1}'.format(self.base_url, page_id),
                            auth=(self.username, self.password),
                            headers=self.headers, data=json.dumps(data),
                            verify=self.verify_ssl).json()
