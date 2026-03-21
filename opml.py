"""
This generates an OPML file of blogs from a CSV file of URLs.

Usage:
    python opml.py [CSV_FILE] [-l]

The CSV file should have two header rows followed by data rows with columns:
    URL, Blog Name, Blog Owner, Home System, Theme

The JSON cache and OPML output files are derived from the CSV filename:
    blogs.csv -> blogs.json (cache), blogs.opml (output)

The JSON cache stores blog metadata and discovered feed URLs so that
subsequent runs without -l skip network requests for already-known feeds.
"""

import argparse
import collections
import csv
import json
from lxml import etree
import os
from pathlib import Path
import sys
import urllib.request, urllib.parse, urllib.error
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup


BLACKLIST = os.getenv("OPML_BLACKLIST", [])
if BLACKLIST:
    BLACKLIST = BLACKLIST.split(",")


def load_blogs_cache(json_file):
    """Load the blogs cache from json_file, returning an empty dict if missing."""
    try:
        with open(json_file, "r") as f:
            try:
                return json.loads(f.read(), object_pairs_hook=collections.OrderedDict)
            except ValueError:
                return {}
    except FileNotFoundError:
        return {}


def update_blogs_cache_from_csv(blogs, csv_file):
    """Load blogs from csv_file and update the blogs cache."""
    cached_blogs = set((url.lower() for url, _ in list(blogs.items())))
    downloaded_blogs = set()

    new_blogs = []

    with open(csv_file) as csvfile:
        csv_reader = csv.reader(csvfile)

        # skip first two lines of this file, they are the header.
        next(csv_reader, None)
        next(csv_reader, None)

        for row in csv_reader:
            # Pad to at least 5 columns so missing trailing fields default to ""
            cols = [col.strip() for col in row] + [""] * 5
            url, title, author, system, theme = cols[:5]

            # Missing URL (or empty row) so skip
            if not url:
                continue

            # Clean up URLs
            url = url.lower()
            if not url.startswith("http"):
                url = "https://" + url

            downloaded_blogs.add(url)

            # Don't include blacklisted URLs. If you want to make your own
            # OSR OPML file full of freedom you can fork this code and go nuts!
            if urlparse(url).netloc in BLACKLIST:
                continue

            # We've already processed this URL
            if url in cached_blogs:
                continue

            # We have a new blog, add it to our cache
            blog = {
                "url": url,
                "xmlUrl": "",
                "title": title,
                "author": author,
                "system": system,
                "theme": theme,
            }

            new_blogs.append(blog)

    print(f"{len(new_blogs)} new blogs:")
    for blog in new_blogs:
        print(f"- {blog['title']} by {blog['author']} ({blog['url']})")
        blogs[blog["url"]] = blog

    removed_blogs = cached_blogs - downloaded_blogs
    print(f"{len(removed_blogs)} removed blogs:")
    for url in removed_blogs:
        blog = blogs.pop(url)
        print(f"- {blog['title']} by {blog['author']} ({url})")


def fetch_metadata_from_feed(feed_url):
    """
    Fetch an RSS/Atom feed and return (title, author) parsed from it.
    Returns empty strings for any field that cannot be found.
    """
    try:
        data = urllib.request.urlopen(feed_url)
        soup = BeautifulSoup(data, features="xml")
    except Exception:
        return "", ""

    title, author = "", ""

    channel = soup.find("channel")
    if channel:
        # RSS feed
        t = channel.find("title")
        a = channel.find("managingEditor") or channel.find("author")
    else:
        feed = soup.find("feed")
        if feed:
            # Atom feed
            t = feed.find("title")
            a = feed.find("author")
            if a:
                name = a.find("name")
                author = name if name else a

    title = t.get_text(strip=True) if t else ""
    author = a.get_text(strip=True) if a else ""

    return title, author


def lookup_feed_urls(blogs, json_file):
    """Lookup the feed URLs for all the blogs that are missing them."""
    bad_blogs = []

    for url, blog_meta_data in list(blogs.items()):
        needs_feed_url = not blog_meta_data["xmlUrl"]
        needs_metadata = not blog_meta_data.get("title") or not blog_meta_data.get("author")

        if not needs_feed_url and not needs_metadata:
            continue

        if needs_feed_url:
            # Fetch the blog's home page to discover the feed URL
            try:
                data = urllib.request.urlopen(url)
                if data.getcode() != 200:
                    bad_blogs.append(
                        (url, "Error fetching feed: {}".format(data.getcode()))
                    )
                    continue
            except IOError as e:
                bad_blogs.append((url, "Error fetching feed: {}".format(e)))
                continue

            # Parse the page and look for alternate link elements
            try:
                soup = BeautifulSoup(data, features="lxml")
                alt = soup.find("link", rel="alternate", type="application/rss+xml")
            except ValueError as e:
                bad_blogs.append((url, "Failed to parse HTML: {}".format(e)))
                continue

            # The feed URL is stored in the href attribute
            if alt is not None:
                blog_meta_data["xmlUrl"] = urljoin(url, alt["href"])
            else:
                bad_blogs.append((url, "Failed to find feed tag."))
                continue

        if not blog_meta_data.get("title") or not blog_meta_data.get("author"):
            feed_title, feed_author = fetch_metadata_from_feed(blog_meta_data["xmlUrl"])
            if not blog_meta_data.get("title"):
                blog_meta_data["title"] = feed_title
            if not blog_meta_data.get("author"):
                blog_meta_data["author"] = feed_author

        # Update the cache file as we find new URLs
        with open(json_file, "w") as f:
            json.dump(blogs, f, indent=2)

    print(f"{len(bad_blogs)} blogs with errors:")
    for url, error in bad_blogs:
        print(f"- {url} ({error})")


def generate_opml_file(blogs, opml_file):
    """Write blogs to opml_file in OPML 2.0 format."""
    opml = etree.Element("opml", version="2.0")
    body = etree.SubElement(opml, "body")
    outline = etree.SubElement(body, "outline", title="Blogs")
    for url, blog_meta_data in list(blogs.items()):
        if not blog_meta_data["xmlUrl"]:
            continue
        blog_meta_data["htmlUrl"] = url
        blog_meta_data["type"] = "rss"
        etree.SubElement(outline, "outline", **blog_meta_data)

    etree.ElementTree(opml).write(opml_file, pretty_print=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate an OPML file from a CSV list of blog URLs."
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        default="osr.csv",
        help="CSV file of blogs to process (default: osr.csv)",
    )
    parser.add_argument(
        "-l",
        "--lookup-feed-urls",
        dest="lookup",
        action="store_true",
        help="Reach out to the Internet to find feed URLs",
    )
    args = parser.parse_args(sys.argv[1:])

    stem = Path(args.csv_file).stem
    json_file = f"{stem}.json"
    opml_file = f"{stem}.opml"

    blogs = load_blogs_cache(json_file)
    update_blogs_cache_from_csv(blogs, args.csv_file)
    if args.lookup:
        lookup_feed_urls(blogs, json_file)
    generate_opml_file(blogs, opml_file)
