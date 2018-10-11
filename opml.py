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

[TODO] Once we're all done, we write the JSON file as an OPML file.
"""

import json
import urllib

from BeautifulSoup import BeautifulSoup

import utfcsv


# Load our local OSR blogs cache
with open('osr.json', 'r') as osr_json:
    try:
        osr_blogs = json.loads(osr_json.read())
    except ValueError:
        osr_blogs = {}

# Load the OSR blogs CSV file previously pulled from Google Docs
with open('osr.csv') as csvfile:
    # skip first line of the file, the header
    next(csvfile, None)

    for row in utfcsv.unicode_csv_reader(csvfile):
        # Each row is: URL, Blog Name, Blog Owner, Home System, Theme
        url, name, author, system, theme = [col.strip() for col in row]

        # Empty row, skip it
        if not url:
            continue

        # Clean up URLs missing a scheme
        if not url.lower().startswith('http'):
            url = 'http://' + url

        # We've already processed this URL
        if url in osr_blogs:
            continue

        # We have a new blog, add it to our cache
        osr_blogs[url] = {
            'xmlUrl': '',
            'name': name,
            'author': author,
            'system': system,
            'theme': theme
        }

# Find the RSS feed for the blogs that are missing them
for url, blog_meta_data in osr_blogs.iteritems():
    if blog_meta_data['xmlUrl']:
        continue

    # Fetch the blogs home page
    print 'Processing {0}'.format(url)
    try:
        data = urllib.urlopen(url)
        if data.getcode() != 200:
            print '{} - Skipped {}'.format(data.getcode(), url)
            continue
    except IOError as e:
        print '{} - Skipped {}'.format(e, url)

    # Parse the page and look for alternate link elements
    try:
        soup = BeautifulSoup(data)
        alt = soup.find('link', rel="alternate", type="application/rss+xml")
    except:
        print 'Failed to parse {}'.format(url)
        continue

    # The feed URL is stored in the href attribute
    if alt is not None:
        blog_meta_data['xmlUrl'] = alt['href']
    else:
        print 'Failed to find feed tag'

    # Update the file as we find new URLs
    with open('osr.json', 'w') as osr_json:
        json.dump(osr_blogs, osr_json, indent=2)



