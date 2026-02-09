# readcomics-cli

Search, browse, and download comics from [readcomiconline.li](https://readcomiconline.li) — straight from your terminal.

Features inline cover art previews, concurrent downloads, and an interactive TUI powered by [Rich](https://github.com/Textualize/rich).

## Install

```sh
# Clone the repo
git clone https://github.com/your-username/readcomics-cli.git
cd readcomics-cli

# Create a virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install the Playwright browser (one-time setup)
playwright install chromium
```

## Usage

```sh
python main.py
```

This launches an interactive session:

1. **Search** — type a comic name
2. **Pick a comic** — see a cover art preview, genres, and summary
3. **Pick issues** — select one, a range, or all
4. **Download** — pages are fetched and downloaded concurrently

### CLI Flags

| Flag | Description |
|---|---|
| `-s`, `--search QUERY` | Skip the search prompt and jump straight to results |
| `-o`, `--output-dir PATH` | Set the download directory (default: `./downloads`) |
| `--no-headless` | Show the browser window (useful for debugging) |

### Examples

```sh
# Interactive mode
python main.py

# Search directly
python main.py --search "batman"

# Download to a custom folder
python main.py -o ~/Comics

# Combine flags
python main.py -s "spider-man" -o ~/Comics
```

### Issue Selection

When choosing which issues to download, you can use:

| Input | Effect |
|---|---|
| `a` | Download all issues |
| `3` | Download issue #3 |
| `1-5` | Download issues 1 through 5 |
| `1,3,7` | Download issues 1, 3, and 7 |
| `1-3,7,10-12` | Mix ranges and individual picks |
| `q` | Go back |

## Dependencies

- [Playwright](https://playwright.dev/python/) — headless browser for scraping pages behind Cloudflare
- [httpx](https://www.python-httpx.org/) — HTTP client for concurrent image downloads
- [Rich](https://github.com/Textualize/rich) — tables, progress bars, styled output
- [Pillow](https://python-pillow.org/) — inline cover art rendering in the terminal

## Project Structure

```
readcomics-cli/
├── main.py              # CLI entry point (interactive TUI)
├── src/
│   ├── __init__.py
│   ├── scraper.py       # ComicScraper — search, issues, image extraction, downloads
│   └── terminal_image.py # Inline image rendering via ANSI half-block characters
├── downloads/           # Default download directory
├── requirements.txt
└── README.md
```

## License

This project is for educational and personal use only.