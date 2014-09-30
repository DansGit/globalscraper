from selenium import webdriver
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
import requests
import feedparser
from goose import Goose
from time import sleep, strftime
import sqlite3
import logging
import config

class RSS_Scraper(object):
    def __init__(self, rss, publication):
        # Initialize some attributes
        self.rss = rss
        self.publication = publication.replace(' ', '_')
        self.logger = logging.getLogger(__name__)
        self.errors = 0
        self.jobs = []



    def scrape(self, pbar, wait=10):
        """Scrapes each new webpage in rss feed."""
        self.logger.info("Scraping rss feed: {}".format(self.rss))
        conn = sqlite3.connect(config.dbpath)


        for entry in self.jobs:
            url = entry['url']
            try:
                # Download webpage with requests
                self.logger.info('Getting "{}" from "{}"'.format(url,
                    self.publication))
                html = _requests_download(url)

                # Try extracting content
                self.logger.info('Extracting content of ' + \
                        '"{}" from "{}"'.format(url, self.publication))
                content = _extract_article(html)

                #If that doesn't work, try using a browser
                #so that AJAX events run.
                if content is False:
                    self.logger.warning('Using browser to download ' + \
                            '"{}" from "{}"'.format(url, self.publication))
                    html = _browser_download(url, wait)
                    content = _extract_article(html)
                else:
                    #Throttle the program, so we don't hit the servers
                    #too hard.
                    sleep(wait)

                # If that STILL doesn't work, raise a parse error
                if content is False:
                    raise ParseError('Unable to extract content from ' + \
                            '"{}" in "{}"'.format(url, self.publication))

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


    def rss_parse(self, limit=20):
        conn = sqlite3.connect(config.dbpath)
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



def _extract_article(html):
    """Removes html boilerplate and extracts article content from html."""
    g = Goose()
    article = g.extract(raw_html=html)
    cleaned = article.cleaned_text
    if cleaned == '':
        return False

    return cleaned

def _browser_download(url, wait):
    try:
        browser = _init_webdriver()
        browser.get(url)
        sleep(wait) # Wait for page to load.
        html = browser.page_source
    finally:
        browser.close()

    return html


def _requests_download(url):
    response = requests.get(url)
    return response.text

def _most_recent_date(conn, publication):
    """Returns the the most recent date in the pub_date column of an sqlite3
    database.
    """
    query = """SELECT pub_date FROM articles
               WHERE publication=?
               ORDER BY pub_date DESC
               LIMIT 1
               """

    params = (publication,)
    result = conn.execute(query, params).fetchone()
    if result:
        return result[0].strip("'")
    else:
        return 0


def _save_article(conn, content, pub_date, headline, publication):
    """Saves article to database."""
    query = """INSERT INTO articles
    (content, pub_date, headline, publication)
    VALUES (?, ?, ?, ?);
    """
    params = (content, pub_date, headline, publication)
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
    fp.add_extension("adblockplusfirefox.xpi")

    # Set the modified profile while creating the browser object
    return webdriver.Firefox(fp)


class ParseError(Exception):
    def __init__(self, msg):
        "Do stuff here later"
        Exception.__init__(self, msg)
