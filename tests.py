import unittest

from redmine2confluence import convert_links
from settings import CONFLUENCE, PROJECTS


class TestLinkConversion(unittest.TestCase):
    def setUp(self):
        self.space = 'SPZ'

    def test_make_url_clickable(self):
        """Should turn url into a clickable link"""
        text = 'Some text with a http://link.com/'
        expected = 'Some text with a <a href="http://link.com/">http://link.com/</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_make_url_clickable_beginning_of_line(self):
        """Should make link clickable when it begins a line"""
        text = 'http://google.com'
        expected = '<a href="http://google.com">http://google.com</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_make_url_clickable_repeated_url(self):
        """Should turn url into a clickable link once when url is repeated"""
        text = 'Some text http://bla.com text http://bla.com'
        expected = ('Some text <a href="http://bla.com">http://bla.com</a>'
                    ' text <a href="http://bla.com">http://bla.com</a>')
        self.assertEqual(convert_links(text, self.space), expected)

    def test_make_issue_number_clickable(self):
        """Should turn old redmine issue # into a clickable link"""
        text = 'Some text #124'
        expected = 'Some text <a href="http://sysrenov1:8080/issues/?jql=%22External%20Issue%20ID%22%20~%20124">124</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link(self):
        """Should turn [[ArticleName]] into clickable link"""
        text = 'Some text [[ArticleName]] more text'
        expected = 'Some text <a href="/display/SPZ/ArticleName">ArticleName</a> more text'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_with_name(self):
        """Should use alt text when available"""
        text = 'Some text [[ArticleName|My Link]]'
        expected = 'Some text <a href="/display/SPZ/ArticleName">My Link</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_of_url(self):
        """Should link URL in conjunction with wiki syntax properly"""
        text = '[[http://www.google.com|My favourite search]]'
        expected = '<a href="http://www.google.com">My favourite search</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_bold_wiki_link(self):
        """Should convert bold wiki link into clickable link"""
        text = '*[[ArticleName]]*'
        expected = '*<a href="/display/SPZ/ArticleName">ArticleName</a>*'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_surrounded_by_text(self):
        """Should convert wiki link surrounded by text into clickable link"""
        text = 'text[[ArticleName]]here'
        expected = 'text<a href="/display/SPZ/ArticleName">ArticleName</a>here'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_with_spaces(self):
        """Should turn spaces into pluses when present in article title"""
        text = '[[Article Name]]'
        expected = '<a href="/display/SPZ/Article+Name">Article Name</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_of_url_with_spaces(self):
        """Should not manipulate spaces when present in url"""
        text = '[[http://google.com/some page/]]'
        expected = '<a href="http://google.com/some page/">http://google.com/some page/</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_underscores(self):
        """Should turn underscores into pluses when present in article title"""
        text = '[[Article_name]]'
        expected = '<a href="/display/SPZ/Article+name">Article_name</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_slashes(self):
        """Should turn remove slashes from URL when present in article title"""
        text = '[[Article/name]]'
        expected = '<a href="/display/SPZ/Articlename">Article/name</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_dots(self):
        """Should turn remove dots from URL when present in article title"""
        text = '[[Article 3.2.10]]'
        expected = '<a href="/display/SPZ/Article+3210">Article 3.2.10</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_of_url_with_underscores(self):
        """Should not manipulate underscores when present in url"""
        text = '[[http://google.com/bla_bla]]'
        expected = '<a href="http://google.com/bla_bla">http://google.com/bla_bla</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_text_within_code_tags_ignored(self):
        """Should not manipulate any text between <code> tags"""
        text = '<code>[[http://google.com/bla_bla]]</code>\n\n<code>\n[[Article_name]]\n</code>'
        self.assertEqual(convert_links(text, self.space), text)

    def test_redmine_links_translation(self):
        """Should re-write hard-coded redmine links to point to Confluence pages"""
        text = ('http://trondheim/redmine/projects/nbrsf/wiki/API_Integration_Test/'
                'http://redmine/redmine/projects/nbrsf/wiki/API_Integration_Test'
                'http://trondheim.phi-tps.local/redmine/projects/nbrsf/wiki/API_Integration_Test/'
                'http://redmine.phi-tps.local/redmine/projects/nbrsf/wiki/API_Integration_Test')

        url = '%s/display/%s/%s' % (CONFLUENCE['url'], PROJECTS['nbrsf'], 'API+Integration+Test')
        html = '<a href="%s">%s</a>' % (url, url)
        expected = '\n'.join([html for _ in range(4)])
        self.assertTrue(convert_links(text, 'nbrsf'), expected)
