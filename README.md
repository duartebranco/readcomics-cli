# readcomics-cli

Search, browse, and download comics from [readcomiconline.li](https://readcomiconline.li) straight from your terminal or browser.

Features inline cover art previews, concurrent downloads, and both a CLI and web interface powered by [Rich](https://github.com/Textualize/rich) and [Flask](https://flask.palletsprojects.com/).

## Features

- 🔍 **Search** - Find comics by name
- 📚 **Browse** - View comic metadata, cover art, genres, and summaries
- 📥 **Download** - Concurrent downloads for maximum speed
- 💻 **CLI** - Interactive terminal interface with Rich TUI
- 🌐 **Web App** - Modern web interface for easy browsing
- 🚀 **Lightweight** - Pure HTTP scraping, no browser automation needed

## Install

```sh
# Clone the repo
git clone https://github.com/duartebranco/readcomics-cli.git
cd readcomics-cli

# Create a virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

### CLI Mode

```sh
python main.py
```

This launches an interactive terminal session:

1. **Search** - type a comic name
2. **Pick a comic** - see a cover art preview, genres, and summary
3. **Pick issues** - select one, a range, or all
4. **Download** - pages are fetched and downloaded concurrently (defaults to `/downloads`)

#### CLI Flags

| Flag | Description |
|---|---|
| `-s`, `--search QUERY` | Skip the search prompt and jump straight to results |
| `-o`, `--output-dir PATH` | Set the download directory (default: `./downloads`) |
| `--no-headless` | (No longer used; kept for backward compatibility) |

### Web Interface

```sh
python web.py
```

Then open your browser to `http://localhost:5000`

#### Web App Options

| Flag | Description |
|---|---|
| `-p`, `--port PORT` | Port to run the server on (default: 5000) |
| `--host HOST` | Host to bind to (default: 127.0.0.1) |
| `--debug` | Run in debug mode |

## How It Works

The scraper uses lightweight HTTP requests with `httpx` or `cloudscraper` to fetch comic data directly from readcomiconline.li. The site embeds image URLs in JavaScript using `lstImages.push("url")` patterns, which we extract with regex.

**Implementation is based on [NOBORU parsers](https://github.com/Creckeryop/NOBORU-parsers)**, which successfully scrape readcomiconline.li using the same HTTP-only approach on PS Vita devices.

This approach is:

- **Fast** - No browser overhead
- **Simple** - Pure Python with minimal dependencies  
- **Proven** - Based on NOBORU's working implementation

### Note on Cloudflare Protection

readcomiconline.li uses Cloudflare protection that may block some automated requests depending on your network/IP. The HTTP approach works for:
- Devices with trusted fingerprints (e.g., PS Vita, as used by NOBORU)
- Networks not flagged by Cloudflare
- Environments with proper cookies/sessions

If you encounter 403 errors, this is a Cloudflare block from your network, not an issue with the scraper logic. The same code works successfully in other environments (as proven by NOBORU).

## Dependencies

- [httpx](https://www.python-httpx.org/) - Modern HTTP client for API requests and downloads
- [cloudscraper](https://github.com/VeNoMouS/cloudscraper) - Cloudflare bypass utility (optional but recommended)
- [Rich](https://github.com/Textualize/rich) - Beautiful terminal UI with tables, progress bars, and styled output
- [Pillow](https://python-pillow.org/) - Image processing for inline cover art rendering in the terminal
- [Flask](https://flask.palletsprojects.com/) - Lightweight web framework for the web interface

## Demo

![Demo](docs/demo.gif)

## License

This project is for educational and personal use only.
