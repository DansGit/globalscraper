import logging
import sys
import csv
from time import clock
import threading
import smtplib
from RSS_Scraper import RSS_Scraper
import datetime
import config
from pyvirtualdisplay import Display
from tempfile import TemporaryFile
from subprocess import Popen
from progressbar import ProgressBar
import sqlite3

DBPATH = "articles.db"

def init_selenium():
    p = Popen(['java', '-jar', 'selenium-server-standalone-2.43.1.jar'],
            stdout=TemporaryFile(),
            stderr=TemporaryFile())

    return p


def chunk(l, n):
    """Divides a list l into n roughly equally sized parts."""
    avg = len(l) / float(n)
    result = []
    last = 0.0
    while last < len(l):
        result.append(l[int(last):int(last + avg)])
        last += avg
    return result



def worker(scrapers, pbar):
    for scraper in scrapers:
        scraper.scrape(pbar)


def email(msg):
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(config.email, config.password)

        msg = '\n' + msg
        server.sendmail(config.email, config.email, msg)
    finally:
        server.quit()


def format_time(seconds):
    return str(datetime.timedelta(seconds=seconds))


def initdb(dbpath):
    conn = sqlite3.connect(dbpath)
    query = """CREATE TABLE IF NOT EXISTS articles
    (
        content TEXT,
        pub_date VARCHAR(100),
        headline VARCHAR(250),
        publication VARCHAR(100)
    );
    """
    conn.execute(query)
    conn.commit()
    conn.close()


def main(num_threads, limit=None):
    # Make sure we have a DB with the correct table.
    initdb(config.dbpath)
    start_time = clock()
    display = Display(visible=0, size=(800, 600))
    display.start()
    logging.basicConfig(filename='globalscraper.log',
            filemode='w',
            level=logging.WARNING)

    scrapers = []
    with open('whitelist_urls.csv') as csvfile:
        whitelist_urls = csv.DictReader(
                csvfile,
                fieldnames=['name', 'url', 'source type', 'language',
                    'direction']
                )
        for row in whitelist_urls:
            scraper = RSS_Scraper(
                    rss=row['url'],
                    publication=row['name']
                    )
            scrapers.append(scraper)

    # Parse RSS feeds
    pbar1 = ProgressBar(len(scrapers))
    print "Parsing RSS feeds..."
    pbar1.start()
    scrapers2 = []
    for scraper in scrapers:
        result = scraper.rss_parse()
        if result:
            scrapers2.append(scraper)
        pbar1.tick()

    jobs = []
    scrapers2 = scrapers2[:limit]
    num_articles = sum([len(x.jobs) for x in scrapers])
    print "Scraping articles..."
    pbar2 = ProgressBar(num_articles)
    pbar2.start()

    # Let's start scraping!
    # This loop will run num_threads times
    for scraper_set in chunk(scrapers2, num_threads):
        t = threading.Thread(target=worker, args=(scraper_set, pbar2))
        t.start()
        jobs.append(t)

    # Wait for all jobs to finish
    for job in jobs:
        job.join()

    # Stop display
    # Todo put this is in a try finally block.
    display.stop()

    # Send email with statistics
    print "Sending email."
    total_time = clock() - start_time
    avg_time = sum([x.elapsed_time for x in scrapers]) / len(scrapers)
    num_articles = sum([x.total for x in scrapers])
    errors = sum([x.errors for x in scrapers])

    msg = "Finished scraping.\n" + \
            "Total time: {}\n".format(format_time(total_time)) + \
            "Average time per scraper: {}\n".format(format_time(avg_time)) + \
            "Number of article extracted: {}\n".format(num_articles) + \
            "Number of errors: {}".format(errors)

    email(msg)


if __name__ == '__main__':
    popen = init_selenium()
    args = sys.argv[1:]
    threads = int(args[0])

    try:
        main(threads)
    finally:
        popen.terminate()




