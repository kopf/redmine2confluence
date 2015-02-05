import unittest

from redmine2confluence import convert_links


class TestLinkConversion(unittest.TestCase):
    def setUp(self):
        self.space = 'SPZ'

    def test_make_url_clickable(self):
        """Should turn url into a clickable link"""
        text = 'Some text with a http://link.com/'
        expected = 'Some text with a <a href="http://link.com/">http://link.com/</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_make_url_clickable_repeated_url(self):
        """Should turn url into a clickable link once when url is repeated"""
        text = 'Some text http://bla.com text'
        expected = 'Some text <a href="http://bla.com">http://bla.com</a> text'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_make_issue_number_clickable(self):
        """Should turn old redmine issue # into a clickable link"""
        text = 'Some text #124'
        expected = 'Some text <a href="http://sysrenov1:8080/issues/?jql=%22External%20Issue%20ID%22%20~%20124">124</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link(self):
        """Should turn [[ArticleName]] into clickable link"""
        text = 'Some text [[ArticleName]] more text'
        expected = 'Some text  <a href="/display/SPZ/ArticleName">ArticleName</a> more text'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_with_name(self):
        """Should use alt text when available"""
        text = 'Some text [[ArticleName|My Link]]'
        expected = 'Some text  <a href="/display/SPZ/ArticleName">My Link</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_of_url(self):
        """Should link URL in conjunction with wiki syntax properly"""
        text = ' [[http://www.google.com|My favourite search]]'
        expected = '  <a href="http://www.google.com">My favourite search</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_with_spaces(self):
        """Should turn spaces into pluses when present in article title"""
        text = ' [[Article Name]]'
        expected = '  <a href="/display/SPZ/Article+Name">Article Name</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_of_url_with_spaces(self):
        """Should not manipulate spaces when present in url"""
        text = ' [[http://google.com/some page/]]'
        expected = '  <a href="http://google.com/some page/">http://google.com/some page/</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_underscores(self):
        """Should turn underscores into pluses when present in article title"""
        text = ' [[Article_name]]'
        expected = '  <a href="/display/SPZ/Article+name">Article_name</a>'
        self.assertEqual(convert_links(text, self.space), expected)

    def test_convert_wiki_link_of_url_with_underscores(self):
        """Should not manipulate underscores when present in url"""
        text = ' [[http://google.com/bla_bla]]'
        expected = '  <a href="http://google.com/bla_bla">http://google.com/bla_bla</a>'
        self.assertEqual(convert_links(text, self.space), expected)

