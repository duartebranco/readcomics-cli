#!/usr/bin/env python3
import argparse
import atexit
import signal
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TaskProgressColumn
from rich.text import Text
from rich.columns import Columns
from rich import box

from src.scraper import ComicScraper
from src.terminal_image import render_image_from_url

console = Console()

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
    console.print("\n\n  [yellow]Interrupted - cleaning up...[/yellow]")
    _cleanup()
    sys.exit(130)


BANNER = r"""[bold cyan]
  ╦═╗╔═╗╔═╗╔╦╗  ╔═╗╔═╗╔╦╗╦╔═╗╔═╗
  ╠╦╝║╣ ╠═╣ ║║  ║  ║ ║║║║║║  ╚═╗
  ╩╚═╚═╝╩ ╩═╩╝  ╚═╝╚═╝╩ ╩╩╚═╝╚═╝[/bold cyan]
[dim]  Search, browse, and download comics from your terminal.[/dim]"""


def prompt_choice(prompt, max_val, allow_quit=True):
    """Prompt the user for a single numeric choice. Returns the 1-based index or None to quit."""
    while True:
        hint = f"1-{max_val}, q to go back" if allow_quit else f"1-{max_val}"
        try:
            raw = console.input(f"  {prompt} [dim]\\[{hint}][/dim]: ").strip().lower()
        except EOFError:
            return None
        if allow_quit and raw in ("q", "quit", "back"):
            return None
        try:
            val = int(raw)
            if 1 <= val <= max_val:
                return val
        except ValueError:
            pass
        console.print(f"  [red]Please enter a number between 1 and {max_val}.[/red]")


def parse_issue_selection(raw, total):
    """
    Parse a user's issue selection string into a sorted list of 0-based indices.

    Supports: "a"/"all", "3", "1-5", "1,3,7", "1-3,7,10-12"
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
        try:
            query = console.input("\n  [bold green]🔍 Search for a comic[/bold green] [dim](q to quit)[/dim]: ").strip()
        except EOFError:
            return None, None
        if query.lower() in ("q", "quit", "exit"):
            return None, None
        if not query:
            continue

        with console.status(f"  [cyan]Searching for \"{query}\"...[/cyan]", spinner="dots"):
            results = scraper.search(query)

        if not results:
            console.print("  [yellow]No comics found. Try a different search term.[/yellow]")
            continue

        return query, results


def display_comics(scraper, results, limit=20):
    """Display search results in a rich table and let the user pick one."""
    shown = results[:limit]

    table = Table(
        title=f"  Found {len(results)} comic(s)" + (f" (showing first {limit})" if len(results) > limit else ""),
        title_style="bold",
        box=box.ROUNDED,
        show_lines=False,
        pad_edge=False,
        expand=False,
    )
    table.add_column("#", style="dim cyan", width=4, justify="right")
    table.add_column("Title", style="bold white", min_width=30)

    for i, comic in enumerate(shown, 1):
        table.add_row(str(i), comic["title"])

    console.print()
    console.print(table)

    choice = prompt_choice("Select a comic", len(shown))
    if choice is None:
        return None

    comic = shown[choice - 1]

    # Show comic info panel with cover art preview
    _show_comic_detail(scraper, comic)

    return comic


def _show_comic_detail(scraper, comic):
    """Fetch and display comic metadata + inline cover art."""
    with console.status("  [cyan]Loading comic details...[/cyan]", spinner="dots"):
        info = scraper.get_comic_info(comic["url"])

    # Build the text info block
    lines = []
    lines.append(f"[bold white]{comic['title']}[/bold white]")
    lines.append("")

    if info.get("publisher"):
        lines.append(f"[bold]Publisher:[/bold] {info['publisher']}")
    if info.get("genres"):
        lines.append(f"[bold]Genres:[/bold]    {info['genres']}")
    if info.get("status"):
        lines.append(f"[bold]Status:[/bold]    {info['status']}")
    if info.get("year"):
        lines.append(f"[bold]Year:[/bold]      {info['year']}")

    if info.get("summary"):
        summary = info["summary"]
        if len(summary) > 200:
            summary = summary[:200].rsplit(" ", 1)[0] + "..."
        lines.append("")
        lines.append(f"[dim]{summary}[/dim]")

    info_text = "\n".join(lines)

    # Try to render cover art inline
    cover_art_str = None
    cover_url = info.get("cover", "")
    if not cover_url:
        cover_url = comic.get("thumbnail", "")

    if cover_url:
        cover_art_str = render_image_from_url(scraper._http, cover_url, max_width=35, max_height=22, indent=0)

    if cover_art_str:
        # Show cover art side-by-side with info using Columns
        console.print()
        console.print(Panel(
            Columns([
                Text.from_ansi(cover_art_str),
                Text.from_markup(info_text),
            ], padding=(0, 3)),
            border_style="cyan",
            padding=(1, 2),
        ))
    else:
        console.print()
        console.print(Panel(info_text, border_style="cyan", padding=(1, 2)))


def display_issues(issues):
    """Display issues in a table and let the user pick which to download."""

    table = Table(
        title=f"  📚 {len(issues)} issue(s) available",
        title_style="bold",
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        pad_edge=False,
        expand=False,
    )
    table.add_column("#", style="dim cyan", width=5, justify="right")
    table.add_column("Issue", style="white", min_width=30)

    if len(issues) <= 30:
        for i, iss in enumerate(issues, 1):
            table.add_row(str(i), iss["title"])
    else:
        for i in range(15):
            table.add_row(str(i + 1), issues[i]["title"])
        table.add_row("...", f"[dim]({len(issues) - 30} more issues)[/dim]")
        for i in range(len(issues) - 15, len(issues)):
            table.add_row(str(i + 1), issues[i]["title"])

    console.print()
    console.print(table)

    console.print()
    console.print("  [bold]Download options:[/bold]")
    console.print("    [cyan]a[/cyan]         all issues")
    console.print("    [cyan]3[/cyan]         single issue")
    console.print("    [cyan]1-5[/cyan]       range of issues")
    console.print("    [cyan]1,3,7[/cyan]     specific issues")
    console.print("    [cyan]q[/cyan]         go back")

    while True:
        try:
            raw = console.input("\n  [bold green]Your choice[/bold green]: ").strip().lower()
        except EOFError:
            return None
        if raw in ("q", "quit", "back"):
            return None

        selected = parse_issue_selection(raw, len(issues))
        if selected is not None:
            return [issues[i] for i in selected]

        console.print("  [red]Invalid selection. Try again.[/red]")


def download_issues(scraper, issues, output_dir):
    """Download a list of issues with a rich progress bar."""
    total_issues = len(issues)
    console.print(f"\n  [bold]⬇ Downloading {total_issues} issue(s) to [cyan]{output_dir}/[/cyan][/bold]\n")

    for issue_idx, issue in enumerate(issues, 1):
        issue_label = f"[{issue_idx}/{total_issues}] {issue['title']}"

        # Phase 1: Fetch page URLs (spinner)
        with console.status(f"  {issue_label}: [dim]fetching pages...[/dim]", spinner="dots"):
            try:
                image_urls = scraper.get_issue_image_urls(issue["url"])
            except KeyboardInterrupt:
                console.print(f"  {issue_label}: [yellow]interrupted[/yellow]")
                raise
            except Exception as e:
                console.print(f"  {issue_label}: [red]FAILED fetching pages ({e})[/red]")
                continue

        if not image_urls:
            console.print(f"  {issue_label}: [yellow]no pages found[/yellow]")
            continue

        # Phase 2: Download images (progress bar)
        try:
            issue_dir = _download_with_progress(
                scraper, issue, image_urls, output_dir, issue_label
            )
            console.print(f"  {issue_label}: [bold green]done ✓[/bold green] [dim]→ {issue_dir}[/dim]")
        except KeyboardInterrupt:
            console.print(f"\n  {issue_label}: [yellow]interrupted[/yellow]")
            raise
        except Exception as e:
            console.print(f"  {issue_label}: [red]FAILED ({e})[/red]")

    console.print(f"\n  [bold green]✅ Finished downloading to [cyan]{output_dir}/[/cyan][/bold green]")


def _download_with_progress(scraper, issue, image_urls, output_dir, issue_label):
    """Handle the concurrent download of an issue's images with a rich progress bar."""
    from urllib.parse import urlparse
    from concurrent.futures import ThreadPoolExecutor, as_completed

    issue_url = issue["url"]
    parsed = urlparse(issue_url)
    path_parts = parsed.path.rstrip("/").split("/")

    comic_title = path_parts[2] if len(path_parts) > 2 else "Unknown"
    comic_title = comic_title.replace("-", " ").replace("_", " ")
    comic_title = " ".join(comic_title.split())

    issue_title = issue["title"].replace("/", "_").replace("\\", "_")
    issue_dir = os.path.join(output_dir, comic_title, issue_title)
    os.makedirs(issue_dir, exist_ok=True)

    total = len(image_urls)
    tasks = []
    for page_num, img_url in enumerate(image_urls, start=1):
        if not img_url:
            continue
        ext = os.path.splitext(urlparse(img_url).path)[1] or ".jpg"
        filename = f"{page_num:03d}{ext}"
        filepath = os.path.join(issue_dir, filename)
        tasks.append((page_num, img_url, filepath))

    with Progress(
        SpinnerColumn(),
        TextColumn(f"  {issue_label}:"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        TextColumn("[dim]{task.completed}/{task.total} pages[/dim]"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("downloading", total=total)

        with ThreadPoolExecutor(max_workers=6) as pool:
            future_to_page = {
                pool.submit(scraper._download_single_page, img_url, filepath): page_num
                for page_num, img_url, filepath in tasks
            }
            for future in as_completed(future_to_page):
                future.result()  # propagate exceptions
                progress.advance(task)

    return issue_dir


def main():
    global _scraper_instance

    parser = argparse.ArgumentParser(
        description="readcomics-cli - search and download comics from your terminal",
    )
    parser.add_argument(
        "-s", "--search",
        type=str,
        default=None,
        metavar="QUERY",
        help="jump straight to searching for a comic by keyword",
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default="downloads",
        metavar="PATH",
        help="directory to save downloaded comics (default: ./downloads)",
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

    console.print(BANNER)

    scraper = ComicScraper(headless=not args.no_headless)
    _scraper_instance = scraper

    try:
        while True:
            # --- Search ---
            if args.search:
                query = args.search
                args.search = None  # only use the CLI arg once
                with console.status(f"  [cyan]Searching for \"{query}\"...[/cyan]", spinner="dots"):
                    results = scraper.search(query)
                if not results:
                    console.print("  [yellow]No comics found for that query.[/yellow]")
                    continue
            else:
                query, results = interactive_search(scraper)
                if results is None:
                    break

            # --- Pick a comic ---
            comic = display_comics(scraper, results)
            if comic is None:
                continue

            with console.status("  [cyan]Loading issues...[/cyan]", spinner="dots"):
                issues = scraper.get_issues(comic["url"])

            if not issues:
                console.print("  [yellow]No issues found for this comic.[/yellow]")
                continue

            # --- Pick issues ---
            selected = display_issues(issues)
            if selected is None:
                continue

            # --- Download ---
            download_issues(scraper, selected, args.output_dir)

            # After downloading, offer to open the folder
            try:
                again = console.input(
                    "\n  [bold green]Search for another comic?[/bold green] [dim](y/n)[/dim]: "
                ).strip().lower()
            except EOFError:
                break
            if again not in ("y", "yes", ""):
                break

    except KeyboardInterrupt:
        console.print("\n\n  [yellow]Interrupted by user.[/yellow]")
    except Exception as e:
        console.print(f"\n  [bold red]Fatal error:[/bold red] {e}", highlight=False)
        sys.exit(1)
    finally:
        _cleanup()
        console.print("\n  [dim]Goodbye! 👋[/dim]\n")


if __name__ == "__main__":
    main()
