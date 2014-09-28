import logging
import sys
import csv
from time import clock
import threading
import smtplib
from RSS_Scraper import RSS_Scraper
import datetime
import config
from tempfile import TemporaryFile
from subprocess import Popen

def init_selenium():
    p = Popen(['java', '-jar', 'selenium-server-standalone-2.43.1.jar'],
            stdout=TemporaryFile(),
            stderr=TemporaryFile())

    return p


def chunk(l, n):
    """Yields successive n sized chunks from l."""
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


def worker(scrapers):
    for scraper in scrapers:
        scraper.scrape()


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


def main(num_threads, limit=None):
    start_time = clock()
    logging.basicConfig(filename='globalscraper.log',
            filemode='w',
            level=logging.INFO)

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
                    dbpath='globalscraper.db',
                    publication=row['name'],
                    )
            scrapers.append(scraper)

    jobs = []
    scrapers = scrapers[:limit]
    divisor = (len(scrapers) / num_threads) + 1

    # Let's start scraping!
    # This loop will run num_threads times
    for scraper_set in chunk(scrapers, divisor):
        t = threading.Thread(target=worker, args=(scraper_set,))
        t.start()
        jobs.append(t)

    # Wait for all jobs to finish
    for job in jobs:
        job.join()

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




