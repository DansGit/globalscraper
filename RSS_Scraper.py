from selenium import webdriver
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile

import feedparser
from goose import Goose
from time import sleep, strftime
import sqlite3
import logging

class RSS_Scraper(object):
    def __init__(self, rss, dbpath, publication):
        # Initialize some attributes
        self.dbpath = dbpath
        self.rss = rss
        self.publication = publication.replace(' ', '_')
        self.logger = logging.getLogger(__name__)
        self.errors = 0
        self.jobs = []

        # Start up the database
        _initdb(self.dbpath, self.publication)


    def scrape(self, pbar, wait=10):
        """Scrapes each new webpage in rss feed."""
        self.logger.info("Scraping rss feed: {}".format(self.rss))
        browser = _init_webdriver()
        conn = sqlite3.connect(self.dbpath)


        for entry in self.jobs:
            url = entry['url']
            try:
                # Load webpage
                self.logger.info('Getting "{}" from "{}"'.format(url,
                    self.publication))
                browser.get(url)
                sleep(wait) # Wait for the page to load

                # Extract Content
                self.logger.info('Extracting content of ' + \
                        '"{}" from "{}"'.format(url, self.publication))
                content = self._extract_article(browser.page_source)

                # Save results
                self.logger.info('Saving results of "{}" from "{}"'.format(
                    url, self.publication))
                _save_article(conn, content, entry['pub_date'], entry['title'],
                        self.publication)
            except ParseError as e:
                self.logger.error(str(e))
                self.errors += 1
            except Exception as e:
                self.logger.error('Error occured while ' + \
                        'scraping "{}"'.format(self.publication),
                        exc_info=True)
                self.errors += 1
            finally:
                pbar.tick()
        conn.close()
        if browser is not None:
            browser.close()


    def rss_parse(self, limit=20):
        conn = sqlite3.connect(self.dbpath)
        newest_date = _most_recent_date(conn, self.publication)
        feed = feedparser.parse(self.rss)

        # Cut items to limit newest.
        items = feed['items'][:limit]

        # Sort feed items ascending.
        try:
            items.sort(key=lambda x: x['published_parsed'])
        except KeyError:
            return False

        # Add feed URLs to a list attribute
        for item in items:
            try:
                item_date = strftime('%Y-%m-%d %T', item['published_parsed'])
                # Make sure we aren't getting old news.
                if item_date > newest_date:
                    entry = {
                            'url': item['link'],
                            'pub_date': item_date,
                            'title': item['title']
                            }

                    self.jobs.append(entry)
            except TypeError:
                logging.warning('Unable to parse date in "{}"'.format(
                    self.publication))

        if self.jobs == []:
            return False
        else:
            return True



    def _extract_article(self, html):
        """Removes html boilerplate and extracts article content from html."""
        g = Goose()
        article = g.extract(raw_html=html)
        cleaned = article.cleaned_text
        if cleaned == '':
            raise ParseError(msg='Unable to extract page in ' + \
                    '"{}"'.format(self.publication))

        return cleaned


def _initdb(dbpath, publication):
    conn = sqlite3.connect(dbpath)
    query = """CREATE TABLE IF NOT EXISTS {table}
    (
        content TEXT,
        pub_date TEXT,
        headline VARCHAR(250)
    );
    """.format(table=publication)
    conn.execute(query)
    conn.commit()
    conn.close()


def _most_recent_date(conn, publication):
    """Returns the the most recent date in the pub_date column of an sqlite3
    database.
    """
    query = """SELECT pub_date FROM {table}
               ORDER BY pub_date DESC
               LIMIT 1
               """.format(table=publication)

    result = conn.execute(query).fetchone()
    if result:
        return result[0].strip("'")
    else:
        return 0


def _save_article(conn, content, pub_date, headline, publication):
    """Saves article to database."""
    query = """INSERT INTO {table}
    (content, pub_date, headline)
    VALUES (?, ?, ?);
    """.format(table=publication)
    params = (content, pub_date, headline)
    """
    params = {
            'content': content,
            'pub_date': repr(pub_date),
            'headline': headline
            }
    """
    conn.execute(query, params)
    conn.commit()


def _init_webdriver():
    # get the Firefox profile object
    fp = FirefoxProfile()

    # Disable CSS
    fp.set_preference('permissions.default.stylesheet', 2)

    # Disable images
    fp.set_preference('permissions.default.image', 2)

    # Disable Flash
    fp.set_preference('dom.ipc.plugins.enabled.libflashplayer.so',
                               'false')

    # Block Pop ups
    fp.set_preference('browser.popups.showPopupBlocker', 'true')

    # Install ad block plus
    # fp.add_extension("adblockplusfirefox.xpi")

    # Set the modified profile while creating the browser object
    return webdriver.Firefox(fp)


class ParseError(Exception):
    def __init__(self, msg):
        "Do stuff here later"
        Exception.__init__(self, msg)
