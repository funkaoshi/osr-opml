"""Tests for opml.py"""

import collections
import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from lxml import etree

from opml import (
    load_blogs_cache,
    update_blogs_cache_from_csv,
    generate_opml_file,
    fetch_metadata_from_feed,
)


# ---------------------------------------------------------------------------
# load_blogs_cache
# ---------------------------------------------------------------------------

def test_load_blogs_cache_missing_file():
    result = load_blogs_cache("/nonexistent/path/to/cache.json")
    assert result == {}


def test_load_blogs_cache_invalid_json(tmp_path):
    bad_json = tmp_path / "cache.json"
    bad_json.write_text("not valid json")
    result = load_blogs_cache(str(bad_json))
    assert result == {}


def test_load_blogs_cache_valid(tmp_path):
    data = {"https://example.com": {"url": "https://example.com", "title": "Example"}}
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps(data))
    result = load_blogs_cache(str(cache))
    assert result == data


def test_load_blogs_cache_preserves_order(tmp_path):
    data = collections.OrderedDict([
        ("https://a.com", {"url": "https://a.com"}),
        ("https://b.com", {"url": "https://b.com"}),
        ("https://c.com", {"url": "https://c.com"}),
    ])
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps(data))
    result = load_blogs_cache(str(cache))
    assert list(result.keys()) == ["https://a.com", "https://b.com", "https://c.com"]


# ---------------------------------------------------------------------------
# update_blogs_cache_from_csv
# ---------------------------------------------------------------------------

CSV_HEADER = (
    "Direct editing is back!\n"
    "URL,Blog Name,Blog Owner,Home System,Theme\n"
)


def make_csv(tmp_path, rows):
    """Write a CSV file with the two-header-line format used by this project."""
    csv_file = tmp_path / "blogs.csv"
    lines = [
        "Intro line\n",
        "URL,Blog Name,Blog Owner,Home System,Theme\n",
    ]
    for row in rows:
        lines.append(",".join(f'"{c}"' if "," in c else c for c in row) + "\n")
    csv_file.write_text("".join(lines))
    return str(csv_file)


def test_update_adds_new_blog(tmp_path):
    csv_file = make_csv(tmp_path, [
        ["https://example.com", "Example Blog", "Author A", "OSE", ""],
    ])
    blogs = {}
    update_blogs_cache_from_csv(blogs, csv_file)
    assert "https://example.com" in blogs
    assert blogs["https://example.com"]["title"] == "Example Blog"
    assert blogs["https://example.com"]["author"] == "Author A"


def test_update_skips_existing_blog(tmp_path):
    csv_file = make_csv(tmp_path, [
        ["https://example.com", "Example Blog", "Author A", "OSE", ""],
    ])
    existing = {
        "https://example.com": {
            "url": "https://example.com",
            "xmlUrl": "https://example.com/feed",
            "title": "Old Title",
            "author": "Old Author",
            "system": "OSE",
            "theme": "",
        }
    }
    update_blogs_cache_from_csv(existing, csv_file)
    # Should not have overwritten existing entry
    assert existing["https://example.com"]["title"] == "Old Title"


def test_update_removes_deleted_blog(tmp_path):
    csv_file = make_csv(tmp_path, [
        ["https://new.com", "New Blog", "Author B", "", ""],
    ])
    blogs = {
        "https://gone.com": {
            "url": "https://gone.com",
            "xmlUrl": "",
            "title": "Gone Blog",
            "author": "Old",
            "system": "",
            "theme": "",
        }
    }
    update_blogs_cache_from_csv(blogs, csv_file)
    assert "https://gone.com" not in blogs
    assert "https://new.com" in blogs


def test_update_normalises_url_to_lowercase(tmp_path):
    csv_file = make_csv(tmp_path, [
        ["https://EXAMPLE.COM/Blog", "Blog", "Author", "", ""],
    ])
    blogs = {}
    update_blogs_cache_from_csv(blogs, csv_file)
    assert "https://example.com/blog" in blogs


def test_update_prepends_https_when_missing(tmp_path):
    csv_file = make_csv(tmp_path, [
        ["example.com", "Blog", "Author", "", ""],
    ])
    blogs = {}
    update_blogs_cache_from_csv(blogs, csv_file)
    assert "https://example.com" in blogs


def test_update_skips_empty_rows(tmp_path):
    csv_file = make_csv(tmp_path, [
        ["", "", "", "", ""],
        ["https://example.com", "Blog", "Author", "", ""],
    ])
    blogs = {}
    update_blogs_cache_from_csv(blogs, csv_file)
    assert len(blogs) == 1


def test_update_blacklist(tmp_path):
    csv_file = make_csv(tmp_path, [
        ["https://blocked.com/page", "Blocked Blog", "Author", "", ""],
        ["https://allowed.com", "Allowed Blog", "Author", "", ""],
    ])
    blogs = {}
    with patch.dict(os.environ, {"OPML_BLACKLIST": "blocked.com"}):
        # Re-import BLACKLIST logic by patching the module-level variable
        import opml
        original = opml.BLACKLIST
        opml.BLACKLIST = ["blocked.com"]
        try:
            update_blogs_cache_from_csv(blogs, csv_file)
        finally:
            opml.BLACKLIST = original

    assert "https://blocked.com/page" not in blogs
    assert "https://allowed.com" in blogs


def test_update_missing_trailing_columns(tmp_path):
    """Rows with fewer than 5 columns should not crash."""
    csv_file = tmp_path / "blogs.csv"
    csv_file.write_text(
        "Intro\n"
        "URL,Blog Name,Blog Owner,Home System,Theme\n"
        "https://short.com,Short Blog\n"
    )
    blogs = {}
    update_blogs_cache_from_csv(blogs, str(csv_file))
    assert "https://short.com" in blogs


# ---------------------------------------------------------------------------
# generate_opml_file
# ---------------------------------------------------------------------------

def test_generate_opml_creates_valid_xml(tmp_path):
    blogs = {
        "https://example.com": {
            "url": "https://example.com",
            "xmlUrl": "https://example.com/feed.rss",
            "title": "Example Blog",
            "author": "Author A",
            "system": "OSE",
            "theme": "",
        }
    }
    opml_file = str(tmp_path / "out.opml")
    generate_opml_file(blogs, opml_file)

    tree = etree.parse(opml_file)
    root = tree.getroot()
    assert root.tag == "opml"
    assert root.get("version") == "2.0"

    outlines = root.findall(".//outline[@type='rss']")
    assert len(outlines) == 1
    assert outlines[0].get("title") == "Example Blog"
    assert outlines[0].get("xmlUrl") == "https://example.com/feed.rss"
    assert outlines[0].get("htmlUrl") == "https://example.com"


def test_generate_opml_skips_blogs_without_feed_url(tmp_path):
    blogs = {
        "https://no-feed.com": {
            "url": "https://no-feed.com",
            "xmlUrl": "",
            "title": "No Feed Blog",
            "author": "Author",
            "system": "",
            "theme": "",
        },
        "https://has-feed.com": {
            "url": "https://has-feed.com",
            "xmlUrl": "https://has-feed.com/rss",
            "title": "Has Feed Blog",
            "author": "Author",
            "system": "",
            "theme": "",
        },
    }
    opml_file = str(tmp_path / "out.opml")
    generate_opml_file(blogs, opml_file)

    tree = etree.parse(opml_file)
    outlines = tree.findall(".//outline[@type='rss']")
    assert len(outlines) == 1
    assert outlines[0].get("title") == "Has Feed Blog"


def test_generate_opml_empty_blogs(tmp_path):
    opml_file = str(tmp_path / "out.opml")
    generate_opml_file({}, opml_file)
    tree = etree.parse(opml_file)
    outlines = tree.findall(".//outline[@type='rss']")
    assert outlines == []


# ---------------------------------------------------------------------------
# fetch_metadata_from_feed
# ---------------------------------------------------------------------------

RSS_FEED = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>My RSS Blog</title>
    <managingEditor>editor@example.com</managingEditor>
  </channel>
</rss>"""

ATOM_FEED = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>My Atom Blog</title>
  <author><name>Atom Author</name></author>
</feed>"""


def _mock_urlopen(content):
    mock_response = MagicMock()
    mock_response.read.return_value = content
    mock_response.__iter__ = lambda self: iter([content])
    mock_response.__enter__ = lambda self: self
    mock_response.__exit__ = MagicMock(return_value=False)
    # BeautifulSoup accepts a file-like object; make it readable
    mock_response.read = MagicMock(return_value=content)
    return mock_response


@patch("opml.urllib.request.urlopen")
def test_fetch_metadata_rss(mock_urlopen):
    mock_urlopen.return_value = io.BytesIO(RSS_FEED)
    title, author = fetch_metadata_from_feed("https://example.com/rss")
    assert title == "My RSS Blog"
    assert "editor@example.com" in author


@patch("opml.urllib.request.urlopen")
def test_fetch_metadata_atom(mock_urlopen):
    mock_urlopen.return_value = io.BytesIO(ATOM_FEED)
    title, author = fetch_metadata_from_feed("https://example.com/atom")
    assert title == "My Atom Blog"
    assert author == "Atom Author"


@patch("opml.urllib.request.urlopen", side_effect=Exception("network error"))
def test_fetch_metadata_network_error(mock_urlopen):
    title, author = fetch_metadata_from_feed("https://example.com/feed")
    assert title == ""
    assert author == ""
