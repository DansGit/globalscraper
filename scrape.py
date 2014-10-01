import logging
import sys
import csv
from time import clock
import threading
import Queue
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


def rssworker(scraper, scrapers, pbar):
    result = scraper.rss_parse()
    if result:
        scrapers.append(scraper)
    pbar.tick()

def scrapeworker(scrapers, queue):
    for scraper in scrapers:
        scraper.scrape(queue)


def dbworker(queue, pbar):
    conn = sqlite3.connect(config.dbpath)
    pbar.start()
    while not pbar.finished:
        result = queue.get()
        if type(result) is dict:
            save_article(conn, result)
        queue.task_done()
        pbar.tick()
    conn.close()


def save_article(conn, article_dict):
    """Saves article to database."""
    query = """INSERT INTO articles
    (content, pub_date, headline, publication, url)
    VALUES (:content, :pub_date, :headline, :publication, :url);
    """
    conn.execute(query, article_dict)
    conn.commit()


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
        publication VARCHAR(100),
        url VARCHAR VARCHAR(250)
    );
    """
    conn.execute(query)
    conn.commit()
    conn.close()


def main(num_threads, limit=None):
    # Make sure we have a DB with the correct table.
    start_time = clock()
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
    initdb(config.dbpath)
    pbar1 = ProgressBar(len(scrapers))
    print "Parsing RSS feeds..."
    pbar1.start()
    scrapers2 = []
    jobs = []
    for scraper in scrapers:
        t = threading.Thread(target=rssworker, args=(scraper, scrapers2, pbar1))
        t.daemon = True
        t.start()
        jobs.append(t)
    for thread in jobs:
        thread.join()


    jobs = []
    scrapers2 = scrapers2[:limit]
    num_articles = sum([len(x.jobs) for x in scrapers2])
    print "Scraping articles..."
    pbar2 = ProgressBar(num_articles)

    # Start display
    display = Display(visible=0, size=(800, 600))
    display.start()

    # Start the database thread
    queue = Queue.Queue()
    dbthread = threading.Thread(target=dbworker, args=(queue, pbar2))
    dbthread.daemon = True
    dbthread.start()

    try:
        # Let's start scraping!
        # This loop will run num_threads times
        for scraper_set in chunk(scrapers2, num_threads):
            t = threading.Thread(target=scrapeworker, args=(scraper_set, queue))
            t.daemon = True
            t.start()
            jobs.append(t)

        # Wait for all jobs to finish
        for job in jobs:
            job.join()

        # Stop database thread
        queue.join()
    finally:
        display.stop()



    # Send email with statistics
    print "Sending email."
    total_time = clock() - start_time
    errors = sum([x.errors for x in scrapers])

    msg = "Finished scraping.\n" + \
            "Total time: {}\n".format(format_time(total_time)) + \
            "Number of article extracted: {}\n".format(num_articles) + \
            "Number of errors: {}".format(errors)

    email(msg)


if __name__ == '__main__':
    popen = init_selenium()
    args = sys.argv[1:]
    threads = int(args[0])

    try:
        main(threads)
    except KeyboardInterrupt:
        print "hi :)"
    finally:
        popen.terminate()




