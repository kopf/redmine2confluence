from HTMLParser import HTMLParser
import re
import traceback

from bs4 import BeautifulSoup
import logbook
from redmine import Redmine
from redmine.exceptions import ResourceAttrError
import requests
import pypandoc
import textile

from confluence import Confluence, Timeout, InvalidXML
from settings import REDMINE, CONFLUENCE, PROJECTS, JIRA_URL

log = logbook.Logger('redmine2confluence')
confluence = Confluence(CONFLUENCE['url'], CONFLUENCE['username'],
                        CONFLUENCE['password'])
redmine = Redmine(REDMINE['url'], key=REDMINE['key'])
STATS = {}


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


def convert_textile(body):
    """Convert textile using pandoc and python-textile.
    If the number of tables in the two doesn't match, go through the pandoc
    version and replace unconverted tables with their equivalents from
    python-textile.
    Otherwise, just return the pandoc version untouched.
    """
    pandoc_conv = pypandoc.convert(body, 'html', format='textile')
    pandoc_soup = BeautifulSoup(pandoc_conv)
    textile_conv = textile.textile(body)
    textile_soup = BeautifulSoup(textile_conv)
    if len(pandoc_soup.find_all('table')) != len(textile_soup.find_all('table')):
        retval = u''
        for line in pandoc_conv.split('\n'):
            if line.startswith('<p>|'):
                retval += textile.textile(line[3:-4].replace('<br />', '\n'))
            else:
                retval += line
    else:
        retval = pandoc_conv
    return retval


def convert_links(body, space):
    """Make links clickable, convert links from old formats to new"""
    link_template = '<a href="%s">%s</a>'
    retval = []
    process = True
    for line in body.split('\n'):
        # Yes, this won't handle nested pre's or code's, but we shouldn't need to.
        if '<code>' in line or '<pre>' in line or '<notextile>' in line:
            process = False
        if process:
            # Convert wiki url links
            wiki_link = ('(http[s]?://(trondheim|redmine)[.phi-tps.local]?/'
                         'redmine/projects/(.*?)/wiki/(.*?)[/]?)')
            for match in set(re.findall(wiki_link, line)):
                url = match[0]
                redmine_project = match[2]
                page_title = match[3].strip('/').replace('_', '+').replace('_', '+')
                try:
                    new_url = '%s/display/%s/%s' % (
                        CONFLUENCE['url'], PROJECTS[redmine_project], page_title)
                except KeyError:
                    log.error('Link translation failed: Project "%s" not mapped!' % redmine_project)
                else:
                    line.replace(url, new_url)

            # Make links clickable
            url_regex = ('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|'
                         '(?:%[0-9a-fA-F][0-9a-fA-F]))+')
            for url in set(re.findall(url_regex, line)):
                line = re.sub('^%s' % re.escape(url), link_template % (url, url), line)
                line = re.sub('\s%s' % re.escape(url), u' '+link_template % (url, url), line)
            # Convert issue #s
            replacement = (' <a href="{0}/issues/?jql=%22External%20Issue%20ID%22%20~%20'
                           '\g<1>">\g<1></a>'.format(JIRA_URL))
            line = re.sub('\s#([0-9]+)', replacement, line)
            # Convert [[Article Name]] and [[Article Name|Some link text here]]
            regex = re.compile('(^|\s+)(\[\[((?P<page_title>[^]]+?)(\|))?'
                               '(?P<display_text>.+?)\]\])')
            matches = set([(match[1], match[3], match[5]) for match in regex.findall(line)])
            for match in matches:
                link_text = match[2]
                target_page = (match[1] or match[2])
                if target_page.startswith('http://') or target_page.startswith('https://'):
                    url = target_page
                else:
                    target_page = target_page.replace(' ', '+').replace('_', '+')
                    url = '/display/%s/%s' % (space, target_page)
                line = line.replace(match[0], link_template % (url, link_text))
        if '</code>' in line or '</pre>' in line or '</notextile>' in line:
            process = True
        retval.append(line)
    return u'\n'.join(retval)


def process(redmine, wiki_page, space, nuclear=False):
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

    body = convert_links(body, space)

    if body.startswith('h1. %s' % title):
        # strip extra repeated title from within body text
        body = body[len('h1. %s' % title):]

    body = convert_textile(body)

    if not nuclear:
        xml_fixer = XMLFixer()
        body = xml_fixer.fix_tags(body)
    else:
        # Use beautifulsoup to clean up stuff like <p><pre>xyz</p></pre>
        body = unicode(BeautifulSoup(body))

    return {
        'title': title,
        'body': body,
        'username': wiki_page.author.refresh().login,
        'display_name': wiki_page.author.name
    }


def add_page(wiki_page, space):
    """Adds page to confluence"""
    processed = process(redmine, wiki_page, space)
    try:
        page = confluence.create_page(
            processed['title'], processed['body'], space,
            processed['username'], processed['display_name'])
    except InvalidXML:
        log.warn('Invalid XML generated. Going for the nuclear option...')
        STATS[space]['nuclear'].append(wiki_page.title)
        processed = process(redmine, wiki_page, space, nuclear=True)
        try:
            page = confluence.create_page(
                processed['title'], processed['body'], space,
                processed['username'], processed['display_name'])
        except InvalidXML:
            import pudb;pudb.set_trace()
    return page


def fix_img_tags(page_id):
    page = confluence.get_page(page_id)
    soup = BeautifulSoup(page['body']['view']['value'])
    changed = False
    for img in soup.find_all('img'):
        if '/' not in img['src']:
            img['src'] = '/download/attachments/%s/%s' % (page_id, img['src'])
            changed = True
    if changed:
        confluence.update_page(page_id, unicode(soup))


def main():
    for proj_name, space in PROJECTS.iteritems():
        STATS[space] = {
            'nuclear': [],
            'failed import': [],
            'failed hierarchical move': []
        }
        created_pages = {}
        log.info(u"Creating space {0}".format(space))
        project = redmine.project.get(proj_name)
        confluence.create_space(space, project.name, project.description)

        # create pages
        for wiki_page in project.wiki_pages:
            try:
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
                        stream=True).raw.read()
                    confluence.add_attachment(
                        page['id'], attachment.filename, data, attachment.description)
                if wiki_page.attachments:
                    fix_img_tags(page['id'])
            except Exception as e:
                msg = 'Uncaught exception during import of %s! Page not imported!'
                log.error(msg % wiki_page.title)
                traceback.print_exc()
                STATS[space]['failed import'].append(wiki_page.title)

        # organize pages hierarchically
        for title, created_page in created_pages.iteritems():
            if created_page.get('parent') not in [None, 'Wiki']:
                log.info(u'Moving "{0}" beneath "{1}"'.format(
                    title, created_page['parent']))
                try:
                    confluence.move_page(
                        created_page['id'],
                        created_pages[created_page['parent']]['id'])
                except Exception as e:
                    msg = 'Uncaught exception during hierarchical move of %s!'
                    log.error(msg % wiki_page.title)
                    traceback.print_exc()
                    STATS[space]['failed hierarchical move'].append(
                        wiki_page.title)


if __name__ == '__main__':
    main()
    log.info('====================')
    log.info('Statistics:')
    log.info('====================')
    for space in STATS:
        for key in STATS[space]:
            log.info('%s:' % key)
            for title in STATS[space][key]:
                log.info('    %s' % title)
        log.info('====================')
