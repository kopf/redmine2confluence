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


BLACKLIST = ['Datenbank_Multitenancy']


class XMLFixer(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.insert(0, tag)

    def handle_endtag(self, tag):
        try:
            self.tags.remove(tag)
        except ValueError:
            pass

    def fix_tags(self, html):
        self.feed(html)
        for tag in self.tags:
            # tags in self.tags are all lower case, so regex that shit:
            regex = re.compile(re.escape('<%s>' % tag), re.IGNORECASE)
            matches = re.findall(regex, html)
            for match in matches:
                fixed = match.replace('<', '&lt;').replace('>', '&gt;')
                html = html.replace(match, fixed)
            if not matches:
                # wasn't matched. Probably <something like this>, with 'like'
                # and 'this' interpreted as tag attributes.
                # try again, just converting the open bracket
                regex = re.compile(re.escape('<%s' % tag), re.IGNORECASE)
                matches = re.findall(regex, html)
                for match in matches:
                    fixed = match.replace('<', '&lt;')
                    html = html.replace(match, fixed)
        return html


def process(redmine, wiki_page):
    """Processes a wiki page, getting all metadata and reformatting body"""
    # Get again, to get attachments:
    wiki_page = wiki_page.refresh(include='attachments')
    # process title
    title = wiki_page.title.replace('_', ' ')
    # process body
    body = urls_to_confluence(wiki_page.text) # translate links
    if body.startswith('h1. %s' % title):
        # strip extra repeated title from within body text
        body = body[len('h1. %s' % title):]
    body = pypandoc.convert(body, 'html', format='textile') # convert textile
    xml_fixer = XMLFixer()
    body = xml_fixer.fix_tags(body)
    ##### build tree object of all wiki pages
    return {
        'title': title,
        'body': body,
        'space': space,
        'username': wiki_page.author.refresh().login,
        'display_name': wiki_page.author.name,
        'attachments': [attachment for attachment in wiki_page.attachments]
    }


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
        _ = len(project.wiki_pages)
        for wiki_page in project.wiki_pages[:project.wiki_pages.total_count]:
            if wiki_page.title in BLACKLIST:
                continue
            log.info(u"Importing: {0}".format(wiki_page.title))
            processed = process(redmine, wiki_page)
            page = confluence.create_page(
                processed['title'], processed['body'], processed['space'],
                processed['username'], processed['display_name'])
            try:
                parent = wiki_page.parent['title']
            except ResourceAttrError:
                parent = None
            created_pages[wiki_page.title] = {
                'id': page['id'], 'parent': parent}
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
            if created_page.get('parent') and created_page['parent'] != 'Wiki':
                log.info(u'Moving "{0}" beneath "{1}"'.format(
                    title, created_page['parent']))
                confluence.move_page(created_page['id'],
                                     created_pages[created_page['parent']]['id'])
