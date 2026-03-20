# OSR OPML Generator

By Ramanan S of [Save vs. Total Party Kill](http://save.vs.totalpartykill.ca/)

With OSR OPML Generator you can produce an [OPML](http://opml.org/) subscription list of OSR (Old School Renaissance) tabletop RPG blogs, ready to import into any feed reader that supports OPML, such as Inoreader or Feedly.

The published OPML file is available at: http://save.vs.totalpartykill.ca/blog/osr-opml/

## Prerequisites

- Python 3.11
- [uv](https://github.com/astral-sh/uv) (`pip install uv`)
- curl (to fetch the blog list)

## Installation and usage

**1. Clone the repository and install dependencies:**

```bash
git clone https://github.com/funkaoshi/osr-opml
cd osr-opml
uv pip install -r requirements.txt
```

**2. Fetch the latest blog list:**

```bash
curl -L "https://docs.google.com/spreadsheets/d/10qvE1s62UA55pleTW54RAZZw-oJQV8yYGZb_UtYo9TE/export?format=csv" -o osr.csv
```

**3. Generate the OPML file:**

```bash
python opml.py -l
```

This fetches each blog's homepage to discover its RSS feed URL, then writes `osr.opml`. Discovered feed URLs are cached in `osr.json` so subsequent runs without `-l` skip the network requests:

```bash
python opml.py
```

## Configuration

To exclude specific blogs from the output, set `OPML_BLACKLIST` to a comma-separated list of domain names before running:

```bash
export OPML_BLACKLIST="example.com,anotherblog.blogspot.com"
python opml.py
```

## Automation

A GitHub Actions workflow runs every Sunday at midnight UTC, on every push to `master`, and on manual trigger. It fetches the latest blog list, regenerates the OPML, and deploys `osr.json` and `osr.opml` to `save.vs.totalpartykill.ca` via SCP.

The workflow requires the following GitHub secrets and variables:

| Name | Type | Description |
|------|------|-------------|
| `SSH_USERNAME` | Secret | SSH username for the deployment server |
| `SSH_KEY` | Secret | SSH password/key for the deployment server |
| `OPML_BLACKLIST` | Secret | Comma-separated list of domains to exclude |
| `KNOWN_HOST` | Variable | SSH known hosts entry for the deployment server |

## Getting help and contributing

File bug reports and feature requests in the [issue tracker](https://github.com/funkaoshi/osr-opml/issues).

The blog list itself is maintained separately as a community Google Spreadsheet. To add or correct a blog entry, refer to the instructions at the top of that sheet.
