import logbook
from redmine import Redmine

from confluence import Confluence
from convert import wiki_to_confluence
from redminelib import get_user
from settings import REDMINE, CONFLUENCE, PROJECTS

log = logbook.Logger('redmine2confluence')


def process(wiki_page):
    """Processes a wiki page, getting all metadata and reformatting body"""
    # Get again, to get attachments:
    wiki_page = redmine.wiki_page.get(
        wiki_page.title, project_id=project.id, include='attachments')
    ##### build tree object of all wiki pages
    user = get_user(wiki_page.author.id)
    body = wiki_to_confluence(wiki_page.text)
    return {
        'title': wiki_page.title,
        'body': body,
        'space': space,
        'username': user['user']['login'],
        'display_name': wiki_page.author.name
    }


def create_page(processed):
    """Creates a wiki page on confluence using parsed result from process()"""
    return confluence.create_page(
        processed['title'], processed['body'], processed['space'],
        processed['username'], processed['display_name'])


if __name__ == '__main__':
    redmine = Redmine(REDMINE['url'], key=REDMINE['key'])
    confluence = Confluence(
        CONFLUENCE['url'], CONFLUENCE['username'], CONFLUENCE['password'])
    for proj_name, space in PROJECTS.iteritems():
        log.info(u"Creating space {0}".format(space))
        project = redmine.project.get(proj_name)
        confluence.create_space(space, project.name, project.description)
        for wiki_page in project.wiki_pages:
            log.info(u"Importing: {0}".format(wiki_page.title))
            page = process(wiki_page)
