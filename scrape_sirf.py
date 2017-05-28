#!/usr/bin/env python

# pip install requests
# pip install -U selenium
# https://chromedriver.storage.googleapis.com/index.html?path=2.29/


from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from sys import platform
import requests
from requests import ConnectionError
import os
import sys
import getopt
import logging
import time
import csv
import re

scrape_url = 'http://sirf-online.org/'
logger = logging.getLogger(os.path.basename(__file__))

scrape_date = time.strftime('%Y-%m-%d %H:%M', time.localtime())
scrape_time_mins = time.strftime('%H%M', time.localtime())


if platform == 'darwin':  # OSX
    driver = webdriver.Chrome()
else:
    driver = webdriver.Chrome('chromedriver.exe')


def _wait_until_loaded():

    loading_class = '.loading'
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, loading_class)))
        logger.info('Loading ...')
    except TimeoutException:
        logger.info('TimeoutException: Loading did not appear')
    except:
        logger.info('UndefinedException: Loading did not appear')

    try:
        WebDriverWait(driver, 30).until_not(EC.presence_of_element_located((By.CSS_SELECTOR, loading_class)))
        logger.info('Loaded.')
    except:
        logger.info('Not loaded in 30 secs')


def scrape(fld, from_date, to_date):

    logger.info('Scraping: {} for all articles'.format(scrape_url))
    driver.get(scrape_url)

    total_counter = 0
    try_max = 0

    while True:
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.load-more'))).click()
            logger.info('Load more clicked upon')
            _wait_until_loaded()
        except TimeoutException:
            # button no longer displays
            logger.info('All articles loaded')
            break
        except:
            # in case anything funky going on
            # try up to three times to click the button
            logger.info('UndefinedException: Try again')
            try_max += 1
            if try_max == 3:
                break

    articles_id = "[id*='post-']"
    all_articles = WebDriverWait(driver, 5).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, articles_id)))
    logger.info('Found {} articles on the site'.format(len(all_articles)))

    title_locator = articles_id + ":nth-of-type({}) .entry-title"
    title_href = articles_id + ":nth-of-type({}) .entry-title a"
    date_locator = articles_id + ":nth-of-type({}) .entry-date"

    metadatas = []
    for counter, article in enumerate(all_articles):
        metadata = []
        metadata.append(scrape_date)

        title = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, title_locator.format(counter + 1)))).text
        logger.info('Title: {}'.format(title.encode('utf-8')))
        metadata.append(title.encode('utf-8'))

        href = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, title_href.format(counter + 1)))).get_attribute('href')
        logger.info('Href: {}'.format(href))
        metadata.append(href)

        date_article = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, date_locator.format(counter + 1)))).text
        logger.info('Title: {}'.format(date_article.encode('utf-8')))
        metadata.append(date_article)

        metadatas.append(metadata)

    logger.info("All articles data scraped.")
    logger.info("Processing individual articles.")

    driver.quit()

    # create download folder
    if not fld:
        downloads_folder = os.path.join(os.path.dirname(__file__), 'download')
    else:
        downloads_folder = os.path.join(os.path.dirname(__file__), fld)
    if not os.path.isdir(downloads_folder):
        os.mkdir(downloads_folder)

    for each_article in metadatas:

        metadata_ = list(each_article)

        post_date = time.strptime(each_article[3], '%B %d, %Y')
        post_date_secs = time.mktime(post_date)

        logger.info('----------------------------------')
        logger.info('Date: %s' % each_article[3])
        logger.info('Transformed to secs: %s' % post_date_secs)

        if from_date < post_date_secs < to_date:
            logger.info('Between start and end date -> Process')

            # download dir
            year_numeric = time.strftime('%Y', post_date)
            month_numeric = time.strftime('%m', post_date)
            day_numeric = time.strftime('%d', post_date)
            logger.info('Year: {}, Month: {}, Day: {}'.format(year_numeric, month_numeric, day_numeric))
            folder_struc = os.path.join(downloads_folder, year_numeric, month_numeric, day_numeric,
                                        scrape_time_mins)
            if not os.path.isdir(folder_struc):
                os.makedirs(folder_struc)
                logger.info('Folders created: %s' % folder_struc)
            else:
                logger.info('Folders already exists: %s' % folder_struc)

            # requesting individual articles
            logger.info('Requesting url: {}'.format(each_article[2]))
            logger.info('Title: {}'.format(each_article[1]))

            # construct a file name
            # ignore non ascii chars
            # strip all non alphanumeric

            file_core = each_article[1].decode('utf-8').encode('ascii', errors='ignore')
            file_core = file_core.replace(' - ', " ")

            split_title = file_core.lower().split(' ')
            file_core = "-".join(split_title)

            regex = re.compile(('[^a-zA-Z-]'))
            file_core = regex.sub('', file_core)
            file_core = file_core.replace('--', '-')
            if file_core.endswith('-'):
                file_core = file_core[:-1]

            # trim file
            # allow max 10 words to reduce the chance of hitting windows length restriction
            while True:
                if file_core.count('-') > 10:
                    file_core = file_core[:file_core.rfind("-")]
                    logger.info('Trimmed file core to: {}'.format(file_core))
                else:
                    logger.info('File core: {}'.format(file_core))
                    break

            for _ in range(3):

                try:
                    # get
                    # nginx returns 403 for non-user agent requests
                    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 '
                                             '(KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

                    request = requests.get(each_article[2], headers=headers, timeout=30, stream=True)
                    file_ = os.path.join(folder_struc, file_core + '.htm')
                    with open(file_, 'wb') as fh:
                        for chunk in request.iter_content(chunk_size=1024):
                            fh.write(chunk)
                    logger.info('Downloaded as: {}'.format(file_))
                    break
                except ConnectionError:
                    logger.info('ConnectionError --> retry up to 3 times')
            else:
                logger.error('ERROR: Failed to download')

            total_counter += 1

            # write metadata
            row = ['Processed Date Time', 'Report Title', 'Report Url', 'Publish Date']
            _write_row(row, os.path.join(folder_struc, file_core + '.metadata.csv'))
            _write_row(metadata_, os.path.join(folder_struc, file_core + '.metadata.csv'))

        else:
            logger.info('Not between start and end date -> Skip')
            logger.info('! {} < {} < {}'.format(from_date, post_date_secs, to_date))

    logger.info('Total articles saved: {}'.format(total_counter))


def _write_row(row, full_path):
    with open(full_path, 'ab') as hlr:
        wrt = csv.writer(hlr, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        wrt.writerow(row)
        logger.debug('Added to %s file: %s' % (full_path, row))


if __name__ == '__main__':
    download_folder = None
    verbose = None
    from_date = '01/01/2000'
    to_date = '01/01/2100'

    log_file = os.path.join(os.path.dirname(__file__), 'logs',
                                time.strftime('%d%m%y', time.localtime()) + "_scraper.log")
    file_hndlr = logging.FileHandler(log_file)
    logger.addHandler(file_hndlr)
    console = logging.StreamHandler(stream=sys.stdout)
    logger.addHandler(console)
    ch = logging.Formatter('[%(levelname)s] %(message)s')
    console.setFormatter(ch)
    file_hndlr.setFormatter(ch)

    argv = sys.argv[1:]
    opts, args = getopt.getopt(argv, "o:vf:t", ["output=", "verbose", "from=", "to="])
    for opt, arg in opts:
        if opt in ("-o", "--output"):
            download_folder = arg
        elif opt in ("-f", "--from"):
            from_date = arg
        elif opt in ("-t", "--to"):
            to_date = arg
        elif opt in ("-v", "--verbose"):
            verbose = True

    str_time = time.strptime(from_date, '%m/%d/%Y')
    from_secs = time.mktime(str_time)

    str_time = time.strptime(to_date, '%m/%d/%Y')
    to_secs = time.mktime(str_time)

    if verbose:
        logger.setLevel(logging.getLevelName('DEBUG'))
    else:
        logger.setLevel(logging.getLevelName('INFO'))

    logger.info('CLI args: {}'.format(opts))
    logger.info('from: {}'.format(from_date))
    logger.info('to: {}'.format(to_date))
    logger.debug('from_in_secs: {}'.format(from_secs))
    logger.debug('to_in_secs: {}'.format(to_secs))

    scrape(download_folder, from_secs, to_secs)