"""
This generates an OPML file of "OSR" blogs, in a somewhat convoluted way.

There is a Google doc of blogs with some extra information about them which is
fetched and stored locally. (You can do so using the following command:

    curl "https://docs.google.com/spreadsheets/d/10qvE1s62UA55pleTW54RAZZw-oJQV8yYGZb_UtYo9TE/export?format=csv" -o

We load a JSON file which is the current information we have about all the OSR
blogs. We update this JSON file if we find anything new. We loop through the
JSON file to look up the RSS/ATOM feeds for the URLs found in the JSON file,
adding them to the file when they are found. The file acts as a sort of cache
in this way.

Once we're all done, we write the JSON file as an OPML file.

We assume a bunch of file names throughout (osr.json, osr.opml, osr.csv).
"""

import argparse
import collections
import json
from lxml import etree
import sys
import urllib

from BeautifulSoup import BeautifulSoup

import utfcsv


def load_blogs_cache():
    """ Load our local OSR blogs cache """
    with open('osr.json', 'r') as osr_json:
        try:
            osr_blogs = json.loads(osr_json.read(), object_pairs_hook=collections.OrderedDict)
        except ValueError:
            osr_blogs = {}

    return osr_blogs


def update_osr_blogs_cache_from_csv(osr_blogs):
    """
    Load the OSR blogs listed in CSV and update osr_blogs local cache.

    This CSV file is pulled down from a google doc outside the context of this
    python script. (If we want to get fancy later we can have Python code do
    everything.)
    """
    new_blogs = []

    # Load the OSR blogs CSV file previously pulled from Google Docs
    with open('osr.csv') as csvfile:
        # skip first line of the file, the header
        next(csvfile, None)

        for row in utfcsv.unicode_csv_reader(csvfile):
            # Each row is: URL, Blog Name, Blog Owner, Home System, Theme
            url, title, author, system, theme = [col.strip() for col in row]

            # Missing URL and Title (or empty row) so skip
            if not url or not title:
                continue

            # Clean up URLs
            url = url.lower()
            if not url.startswith('http'):
                url = 'http://' + url

            # We've already processed this URL
            if url in osr_blogs:
                continue

            # We have a new blog, add it to our cache
            osr_blogs[url] = {
                'xmlUrl': '',
                'title': title,
                'author': author,
                'system': system,
                'theme': theme
            }

            new_blogs.append((author, title, url))

    print u"{0} new blogs:".format(len(new_blogs))
    for author, title, url in new_blogs:
        print u"- {0} by {1} ({2})".format(title, author, url)


def lookup_feed_urls(osr_blogs):
    """ Lookup the feed URLs for all the blogs that missing them. """
    bad_blogs = []

    for url, blog_meta_data in osr_blogs.iteritems():
        if blog_meta_data['xmlUrl']:
            continue

        # Fetch the blogs home page
        try:
            data = urllib.urlopen(url)
            if data.getcode() != 200:
                bad_blogs.append((url, "Error fetching feed."))
                continue
        except IOError as e:
            bad_blogs.append((url, "Error fetching feed."))
            continue

        # Parse the page and look for alternate link elements
        try:
            soup = BeautifulSoup(data)
            alt = soup.find('link', rel="alternate", type="application/rss+xml")
        except:
            bad_blogs.append((url, "Failed to parse HTML."))
            continue

        # The feed URL is stored in the href attribute
        if alt is not None:
            blog_meta_data['xmlUrl'] = alt['href']
        else:
            bad_blogs.append((url, "Failed to find feed tag."))
            continue

        # Update the file as we find new URLs
        with open('osr.json', 'w') as osr_json:
            json.dump(osr_blogs, osr_json, indent=2)

    print u"{0} blogs with errors:".format(len(bad_blogs))
    for url, error in bad_blogs:
        print u"- {0} ({1})".format(url, error)


def generate_opml_file(osr_blogs):
    # Write an OPML file!
    opml = etree.Element('opml', version="2.0")
    body = etree.SubElement(opml, 'body')
    outline = etree.SubElement(body, 'outline', title="OSR Blogs")
    for url, blog_meta_data in osr_blogs.iteritems():
        if not blog_meta_data['xmlUrl']:
            continue
        blog_meta_data['htmlUrl'] = url
        etree.SubElement(outline, 'outline', **blog_meta_data)

    with open('osr.opml', 'w') as osr_opml:
        etree.ElementTree(opml).write(osr_opml, pretty_print=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-l', '--lookup-feed-urls', dest='lookup', action='store_true',
        help="Reach out to the Internet to find feed URLs"
    )
    args = parser.parse_args(sys.argv[1:])

    osr_blogs = load_blogs_cache()
    update_osr_blogs_cache_from_csv(osr_blogs)
    if args.lookup:
        lookup_feed_urls(osr_blogs)
    generate_opml_file(osr_blogs)
