# redmine2confluence

redmine2confluence is a tool for importing redmine wikis to Confluence.

It has a few main strengths:

* Page ownership is preserved
* Page hierarchies are preserved
* Attachments are imported. Image attachments displayed within wiki pages are re-written so they continue to work.
* URLs are made clickable.
* Links to redmine issues (e.g. `#12345`) are turned into links to the equivalent issues on your JIRA instance.
* URLs pointing to other redmine wiki pages rewritten as links to the equivalent Confluence pages.

Its main strength, however, is that this seems to be the only all-in-one solution for performing this kind of migration.

## Disclaimer

This code was written specifically to address a single import case, and may not behave as you'd like or expect it to.

Back up your data before proceeding. This software is provided "as is".

## Instructions

* Check out the repository
* Add a `settings.py` file. Here is an example:

````
REDMINE = {
    'url': 'http://my_redmine_server/redmine', # No trailing slash
    'key': 'my admin user api key'
}

CONFLUENCE = {
    'url': 'http://my_confluence_server:8090',
    'username': 'root',
    'password': 'root'
}

JIRA_URL = 'http://my_jira_server:8080'

PROJECTS = {
    "pets", "PTS", # in the form: "REDMINE_PROJECT_ID": "CONFLUENCE_SPACE_ID (short)"
}
````

* Run `./redmine2confluence.py`
