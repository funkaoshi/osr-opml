import json
import requests
import collections
from lxml import etree
from datetime import datetime, timezone
import csv


def regenerate_post_frequencies():
    with open("osr.json") as f:
        osr_blogs = json.load(f)

    post_frequency = {}

    for i, blog in enumerate(osr_blogs.values()):
        print(blog["title"])
        xml_url = blog["xmlUrl"]
        if not xml_url:
            continue

        try:
            r = requests.get(xml_url)
        except IOError as e:
            print("Failed to fetch XML: {e}")
            continue

        if r.status_code != 200:
            continue

        try:
            tree = etree.fromstring(r.content)
        except etree.XMLSyntaxError:
            print("Failed to parse XML")
            continue

        try:
            pub_dates = [
                datetime.strptime(item.find("pubDate").text, "%a, %d %b %Y %H:%M:%S %z")
                for item in tree.iter("item")
            ]
        except ValueError:
            print("Failed to parse pubDate")
            continue

        counts = collections.Counter([date.year for date in pub_dates])

        if not pub_dates:
            continue

        try:
            score = len(pub_dates) * (
                (datetime.now(timezone.utc) - max(pub_dates)).days
                / (max(pub_dates) - min(pub_dates)).days
            )
        except ZeroDivisionError:
            score = 100000

        post_frequency[blog["title"]] = {
            "dates": [(d.year, d.month, d.day) for d in pub_dates],
            "score": score,
        }

    json.dump(post_frequency, open("post_frequency.json", "w"))

with open("post_frequency.json") as f:
    post_frequency = json.load(f)

with open("post_frequency.csv", "w") as f:
    writer = csv.writer(f)
    writer.writerow(["blog", "score", "dates"])
    for blog, data in post_frequency.items():
        dates = [
            f"{year}-{month:02}-{day:02}"
            for year, month, day in data["dates"]
        ]
        writer.writerow([blog, data["score"], *dates])
