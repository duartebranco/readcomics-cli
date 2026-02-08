#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from scraper import ComicScraper


def main():
    scraper = ComicScraper()

    try:
        results = scraper.search("hulk")
        if not results:
            print("No comics found for query")
            return

        print("Found comics:")
        for i, r in enumerate(results[:5], start=1):
            print(f"{i}. {r.get('title')}")

        comic = results[0]
        issues = scraper.get_issues(comic["url"])

        if not issues:
            print(f"No issues found for comic: {comic.get('title')}")
            return

        num_pages = scraper.get_num_pages(issues[0]["url"])
        print(f"Number of pages: {num_pages}")

        print(f"\nDownloading: {issues[0].get('title')}")
        scraper.download_issue(issues[0])

    finally:
        # Ensure resources are cleaned up even if something goes wrong.
        try:
            scraper.close()
        except Exception:
            # Suppress cleanup errors to avoid masking the original exception.
            pass


if __name__ == "__main__":
    main()
