from HTMLParser import HTMLParser
import re

import logbook
from redmine import Redmine
from redmine.exceptions import ResourceAttrError
import requests
import pypandoc

from confluence import Confluence, Timeout
from convert import urls_to_confluence
from settings import REDMINE, CONFLUENCE, PROJECTS

log = logbook.Logger('redmine2confluence')


BLACKLIST = []


def process(redmine, wiki_page):
    """Processes a wiki page, getting all metadata and reformatting body"""
    # Get again, to get attachments:
    wiki_page = wiki_page.refresh(include='attachments')
    # process title
    title = wiki_page.title.replace('_', ' ')
    # process body
    ## HTMLEncode ALL tags
    body = wiki_page.text.replace('<', '&lt;').replace('>', '&gt;')
    # HTMLDecode redmine tags
    body = body.replace('&lt;code&gt;', '<code>').replace('&lt;/code&gt;', '</code>')
    body = body.replace('&lt;notextile&gt;', '<notextile>').replace('&lt;/notextile&gt;', '</notextile>')
    body = body.replace('&lt;pre&gt;', '<pre>').replace('&lt;/pre&gt;', '</pre>')
    # translate links
    body = urls_to_confluence(body)
    if body.startswith('h1. %s' % title):
        # strip extra repeated title from within body text
        body = body[len('h1. %s' % title):]
    body = pypandoc.convert(body, 'html', format='textile') # convert textile
    return {
        'title': title,
        'body': body,
        'username': wiki_page.author.refresh().login,
        'display_name': wiki_page.author.name,
        'attachments': [attachment for attachment in wiki_page.attachments]
    }


def get_total_count(project_id):
    """Workaround for bug in python-redmine"""
    url = '%s/projects/%s/wiki/index.json?key=%s'
    r = requests.get(url % (REDMINE['url'], project_id, REDMINE['key'])).json()
    return len(r['wiki_pages'])


if __name__ == '__main__':
    redmine = Redmine(REDMINE['url'], key=REDMINE['key'])
    confluence = Confluence(
        CONFLUENCE['url'], CONFLUENCE['username'], CONFLUENCE['password'])
    for proj_name, space in PROJECTS.iteritems():
        created_pages = {}
        log.info(u"Creating space {0}".format(space))
        project = redmine.project.get(proj_name)
        confluence.create_space(space, project.name, project.description)

        # create pages
        for wiki_page in project.wiki_pages[:get_total_count(proj_name)]:
            if wiki_page.title in BLACKLIST:
                continue
            log.info(u"Importing: {0}".format(wiki_page.title))
            processed = process(redmine, wiki_page)
            page = confluence.create_page(
                processed['title'], processed['body'], space,
                processed['username'], processed['display_name'])
            try:
                parent = wiki_page.parent['title']
            except ResourceAttrError:
                parent = None
            created_pages[wiki_page.title] = {'id': page['id'], 'parent': parent}
            for attachment in processed['attachments']:
                log.info(u'Adding attachment: {0} ({1} bytes)'.format(
                    attachment.filename, attachment.filesize))
                data = requests.get(
                    u'{0}?key={1}'.format(attachment.content_url, REDMINE['key']),
                    stream=True)
                retry = True
                while retry:
                    try:
                        confluence.add_attachment(
                            page['id'], attachment.filename, data.raw, attachment.description)
                    except Timeout:
                        log.warn('Timed out. Retrying...')
                    else:
                        retry = False

        # organize pages hierarchically
        for title, created_page in created_pages.iteritems():
            if created_page.get('parent') not in [None, 'Wiki']:
                log.info(u'Moving "{0}" beneath "{1}"'.format(
                    title, created_page['parent']))
                confluence.move_page(created_page['id'],
                                     created_pages[created_page['parent']]['id'])
