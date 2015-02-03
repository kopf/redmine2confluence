from HTMLParser import HTMLParser
import re

from bs4 import BeautifulSoup
import logbook
from redmine import Redmine
from redmine.exceptions import ResourceAttrError
import requests
import pypandoc

from confluence import Confluence, Timeout, InvalidXML
from convert import urls_to_confluence
from settings import REDMINE, CONFLUENCE, PROJECTS

log = logbook.Logger('redmine2confluence')
confluence = Confluence(CONFLUENCE['url'], CONFLUENCE['username'],
                        CONFLUENCE['password'])
redmine = Redmine(REDMINE['url'], key=REDMINE['key'])

BLACKLIST = []


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


def process(redmine, wiki_page, nuclear=False):
    """Processes a wiki page, getting all metadata and reformatting body"""
    # Get again, to get attachments:
    wiki_page = wiki_page.refresh(include='attachments')
    # process title
    title = wiki_page.title.replace('_', ' ')
    # process body
    body = wiki_page.text
    if nuclear:
        ## HTMLEncode ALL tags
        body = body.replace('<', '&lt;')
        # HTMLDecode redmine tags
        body = body.replace('&lt;code>', '<code>').replace('&lt;/code>', '</code>')
        body = body.replace('&lt;notextile>', '<notextile>').replace('&lt;/notextile>', '</notextile>')
        body = body.replace('&lt;pre>', '<pre>').replace('&lt;/pre>', '</pre>')
        # Use beautifulsoup to clean up stuff like <p><pre>xyz</p></pre>
        body = unicode(BeautifulSoup(body))
    # translate links
    body = urls_to_confluence(body)
    if body.startswith('h1. %s' % title):
        # strip extra repeated title from within body text
        body = body[len('h1. %s' % title):]
    body = pypandoc.convert(body, 'html', format='textile') # convert textile
    if not nuclear:
        xml_fixer = XMLFixer()
        body = xml_fixer.fix_tags(body)
    return {
        'title': title,
        'body': body,
        'username': wiki_page.author.refresh().login,
        'display_name': wiki_page.author.name
    }


def get_total_count(project_id):
    """Workaround for bug in python-redmine"""
    url = '%s/projects/%s/wiki/index.json?key=%s'
    r = requests.get(url % (REDMINE['url'], project_id, REDMINE['key'])).json()
    return len(r['wiki_pages'])


def add_page(wiki_page, space):
    """Adds page to confluence"""
    processed = process(redmine, wiki_page)
    try:
        page = confluence.create_page(
            processed['title'], processed['body'], space,
            processed['username'], processed['display_name'])
    except InvalidXML:
        log.warn('Invalid XML generated. Going for the nuclear option...')
        processed = process(redmine, wiki_page, nuclear=True)
        try:
            page = confluence.create_page(
                processed['title'], processed['body'], space,
                processed['username'], processed['display_name'])
        except InvalidXML:
            import pudb;pudb.set_trace()
    return page


def main():
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
            page = add_page(wiki_page, space)
            try:
                parent = wiki_page.parent['title']
            except ResourceAttrError:
                parent = None
            created_pages[wiki_page.title] = {'id': page['id'], 'parent': parent}
            for attachment in wiki_page.attachments:
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


if __name__ == '__main__':
    main()
