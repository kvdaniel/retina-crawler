from rss_feed_parser import *
from writers import *
from article import Article
from downloaders import *
import multiprocessing
import sys

class ModularCrawler(object):
    def _get_writer(self, args):
        """Create and return an output writer based on the given input value.

        Arguments:
        args -- The args variable given to the crawler.

        Return the appropriate writer requested. Will raise an exception if something goes wrong.
        """
        try:
            output = args["output"].lower()
        except KeyError:
            raise ValueError("Must specify an output type.")
        except AttributeError:
            raise ValueError("'output' must be a string.")

        if output == "file":
            return FileWriter()
        elif output == "mongo":
            try:
                mongo_kw_args = args['mongo_params']
            except KeyError:
                raise ValueError("'mongo_params' must be specified when writing to MongoDB.")
            try:
                return MongoWriter(**mongo_kw_args)
            except TypeError:
                raise ValueError("'mongo_params' requires a host and port. The following was given: %s" % mongo_kw_args)
        elif output == "print":
            return PrintWriter()
        else:
            raise ValueError("Could not interpret the given output type: %s" % output)

    def _get_threads(self, args):
        """Determine the number of threads/processes the crawler should work with.

        Arguments:
        args -- The args variable given to the crawler.

        Return an integer representing the number of processes to spawn for this crawler. Will 
        raise an exception if something goes wrong.
        """
        try:
            threads = int(args["threads"])
        except KeyError:
            raise ValueError("Must specify the number of threads the crawler should work with.")
        except ValueError:
            raise ValueError("Threads must be an integer.")
        if threads < 0:
            raise ValueError("Threads must be a positive integer.")
        # 0 is interpreted as make as many threads as there are cores.
        if threads == 0:
            threads = multiprocessing.cpu_count()
        return threads

    def _get_downloader(self, writer, threads):
        """Create and return a Downloader for downloading articles with.

        Arguments:
        writer -- The output writer to use.
        threads -- The number of threads to utilize.
        
        Return a Downloader for downloading articles.
        """
        if threads == 1:
            return SingleThreadedDownloader(writer)
        else:
            return MultiProcessDownloader(threads, writer)

    def _process_urls(self):
        """Queue all manually entered URLs for the crawler.

        Running this method more than once does nothing.
        """
        if self._urls is None:
            return
        try:
            for url in self._urls:
                # makes sure urls after a bad url are still queued
                try:
                    article = Article.create(url)
                    self._downloader.queue_article(article)
                except Exception, e:
                    print str(url) + " is bad"
                    print e
        except TypeError:
            raise ValueError("'urls' must be a list of article URLs to process.")
        finally:
            # Regardless of it we successfully queued all of the links, we don't want to try again.
            self._urls = None

    def _process_feeds(self):
        """Queue all articles found in the provided RSS feeds."""
        if self._feeds is None:
            return

        try:
            for feed in self._feeds:
                # all of the nested try excepts
                try:
                    feed_parser = RssLinkParser(feed)
                    for article in feed_parser.get_new_articles():
                        self._downloader.queue_article(article)
                except Exception, e:
                    print feed + " is bad"
                    print e
        except TypeError:
            raise ValueError("'feeds' must be a list of RSS feed URLs to process.")

    def __init__(self, args):
        writer = self._get_writer(args)
        threads = self._get_threads(args)
        downloader = self._get_downloader(writer, threads)

        try:
            self._urls = args["urls"]
        except KeyError:
            # Passing in individual URLs is optional.
            self._urls = None

        try:
            self._feeds = args["feeds"]
        except KeyError:
            # Passing in feeds is optional.
            self._feeds = None

        if self._urls is None and self._feeds is None:
            raise ValueError("No URLs or feeds were specified for processing.")

        self._downloader = downloader

    def crawl(self):
        """Crawl all provided feeds and URLs for content.
        
        This method is designed to be called repeatedly. It will block until completion. It is 
        designed to never raise exceptions.
        
        Return True if the crawl method should be called again. 
        """
        self._process_urls()
        self._process_feeds()
        self._downloader.process_all()

        return self._feeds is not None

class SeveralRSSMongoRunner(object):
    def __init__(self, config):
        self._rss_parser = MultiRSSLinkParsers(config['feeds'])
        mongo_kw_args = config['mongo_params'] if 'mongo_params' in config else {}
        
        self._article_writer = MongoWriter(**mongo_kw_args)

    def run(self):
        for link in self._rss_parser.get_new_links():
            article = Article.create(link)
            self._article_writer.write(article.to_dict())

class SimpleRunner(object):
    def __init__(self):
        self._rssParser = RssLinkParser('http://rss.cnn.com/rss/edition.rss')
        self._article_writer = FileWriter()

    def run(self):
        for link in self._rssParser.get_new_links():
            article = Article.create(link)
            self._article_writer.write(article.to_dict())
