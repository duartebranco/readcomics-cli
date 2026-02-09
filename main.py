#!/usr/bin/env python3
import argparse
import atexit
import signal
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from src.scraper import ComicScraper

# Global reference so signal handlers and atexit can clean up
_scraper_instance = None


def _cleanup():
    """Ensure the scraper's browser and resources are released."""
    global _scraper_instance
    if _scraper_instance is not None:
        try:
            _scraper_instance.close()
        except Exception:
            pass
        _scraper_instance = None


def _signal_handler(signum, frame):
    """Handle termination signals gracefully."""
    print("\n\n  Interrupted — cleaning up...")
    _cleanup()
    sys.exit(130)


def prompt_choice(prompt, max_val, allow_quit=True):
    """Prompt the user for a single numeric choice. Returns the 1-based index or None to quit."""
    while True:
        hint = f"1-{max_val}, q to go back" if allow_quit else f"1-{max_val}"
        raw = input(f"{prompt} [{hint}]: ").strip().lower()
        if allow_quit and raw in ("q", "quit", "back"):
            return None
        try:
            val = int(raw)
            if 1 <= val <= max_val:
                return val
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {max_val}.")


def parse_issue_selection(raw, total):
    """
    Parse a user's issue selection string into a sorted list of 0-based indices.

    Supports:
      "a" / "all"    -> all issues
      "3"            -> single issue
      "1-5"          -> range (inclusive)
      "1,3,7"        -> comma-separated
      "1-3,7,10-12"  -> mixed
    """
    raw = raw.strip().lower()
    if raw in ("a", "all"):
        return list(range(total))

    indices = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            bounds = part.split("-", 1)
            try:
                lo, hi = int(bounds[0]), int(bounds[1])
                for i in range(lo, hi + 1):
                    if 1 <= i <= total:
                        indices.add(i - 1)
            except ValueError:
                return None
        else:
            try:
                val = int(part)
                if 1 <= val <= total:
                    indices.add(val - 1)
            except ValueError:
                return None

    return sorted(indices) if indices else None


def interactive_search(scraper):
    """Prompt the user for a search query and return results, or None to quit."""
    while True:
        query = input("\n🔍 Search for a comic (q to quit): ").strip()
        if query.lower() in ("q", "quit", "exit"):
            return None, None

        if not query:
            continue

        print(f"  Searching for \"{query}\"...")
        results = scraper.search(query)

        if not results:
            print("  No comics found. Try a different search term.")
            continue

        return query, results


def display_comics(results, limit=20):
    """Display search results and let the user pick one. Returns the chosen comic dict or None."""
    shown = results[:limit]
    print(f"\n  Found {len(results)} comic(s):" + (f" (showing first {limit})" if len(results) > limit else ""))
    for i, comic in enumerate(shown, 1):
        print(f"    {i:>3}. {comic['title']}")

    choice = prompt_choice("\n  Select a comic", len(shown))
    if choice is None:
        return None
    return shown[choice - 1]


def display_issues(issues):
    """Display issues and let the user pick which to download. Returns a list of issue dicts or None."""
    print(f"\n  📚 {len(issues)} issue(s) available:")

    # Show in a compact format; if there are many, show first/last with indication
    if len(issues) <= 30:
        for i, iss in enumerate(issues, 1):
            print(f"    {i:>3}. {iss['title']}")
    else:
        for i in range(10):
            print(f"    {i + 1:>3}. {issues[i]['title']}")
        print(f"    ... ({len(issues) - 20} more) ...")
        for i in range(len(issues) - 10, len(issues)):
            print(f"    {i + 1:>3}. {issues[i]['title']}")

    print("\n  Download options:")
    print("    a       → all issues")
    print("    3       → single issue")
    print("    1-5     → range of issues")
    print("    1,3,7   → specific issues")
    print("    q       → go back")

    while True:
        raw = input("\n  Your choice: ").strip().lower()
        if raw in ("q", "quit", "back"):
            return None

        selected = parse_issue_selection(raw, len(issues))
        if selected is not None:
            return [issues[i] for i in selected]

        print("  Invalid selection. Try again.")


def download_issues(scraper, issues, output_dir):
    """Download a list of issues with progress feedback."""
    total_issues = len(issues)
    print(f"\n  ⬇ Downloading {total_issues} issue(s) to ./{output_dir}/\n")

    for issue_idx, issue in enumerate(issues, 1):
        label = f"  [{issue_idx}/{total_issues}] {issue['title']}"

        def on_page_done(page_num, total_pages, _label=label):
            bar_width = 25
            filled = int(bar_width * page_num / total_pages) if total_pages else bar_width
            bar = "█" * filled + "░" * (bar_width - filled)
            pct = (page_num * 100 // total_pages) if total_pages else 100
            print(f"\r{_label}: {bar} {page_num}/{total_pages} ({pct}%)", end="", flush=True)

        try:
            print(f"\r{label}: fetching page list...", end="", flush=True)
            issue_dir = scraper.download_issue(issue, output_dir=output_dir, on_page_done=on_page_done)
            print(f"\r{label}: done ✓ → {issue_dir}" + " " * 10)
        except KeyboardInterrupt:
            print(f"\r{label}: interrupted" + " " * 30)
            raise
        except Exception as e:
            print(f"\r{label}: FAILED ✗ ({e})" + " " * 30)

    print(f"\n  ✅ Finished downloading to ./{output_dir}/")


def main():
    global _scraper_instance

    parser = argparse.ArgumentParser(
        description="readcomics-cli — search and download comics from readcomiconline.li",
    )
    parser.add_argument(
        "-s", "--search",
        type=str,
        default=None,
        help="jump straight to searching for a comic by keyword",
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default="downloads",
        help="directory to save downloaded comics (default: downloads)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="show the browser window (useful for debugging)",
    )
    args = parser.parse_args()

    # Register cleanup handlers before anything is allocated
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    atexit.register(_cleanup)

    print("╔══════════════════════════════════════╗")
    print("║         readcomics-cli               ║")
    print("╚══════════════════════════════════════╝")

    scraper = ComicScraper(headless=not args.no_headless)
    _scraper_instance = scraper

    try:
        while True:
            # --- Search ---
            if args.search:
                query = args.search
                args.search = None  # only use the CLI arg once
                print(f"\n🔍 Searching for \"{query}\"...")
                results = scraper.search(query)
                if not results:
                    print("  No comics found for that query.")
                    continue
            else:
                query, results = interactive_search(scraper)
                if results is None:
                    break

            # --- Pick a comic ---
            comic = display_comics(results)
            if comic is None:
                continue

            print(f"\n  Loading issues for \"{comic['title']}\"...")
            issues = scraper.get_issues(comic["url"])

            if not issues:
                print("  No issues found for this comic.")
                continue

            # --- Pick issues ---
            selected = display_issues(issues)
            if selected is None:
                continue

            # --- Download ---
            download_issues(scraper, selected, args.output_dir)

            # After downloading, loop back to search
            again = input("\n  Search for another comic? (y/n): ").strip().lower()
            if again not in ("y", "yes", ""):
                break

    except KeyboardInterrupt:
        print("\n\n  Interrupted by user.")
    except Exception as e:
        print(f"\n  Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        _cleanup()
        print("\nGoodbye! 👋")


if __name__ == "__main__":
    main()