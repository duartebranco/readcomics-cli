#!/usr/bin/env python3
"""
Flask web application for readcomics-cli.
Provides a web interface for searching and downloading comics.
"""

from flask import Flask, render_template, request, jsonify, send_file, session
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scraper import ComicScraper

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Global scraper instance
scraper = ComicScraper()

@app.route('/')
def index():
    """Home page with search bar."""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """Search for comics and return results as JSON."""
    query = request.json.get('query', '').strip()
    if not query:
        return jsonify({'error': 'No search query provided'}), 400
    
    try:
        results = scraper.search(query)
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/comic/<path:comic_slug>')
def comic_details(comic_slug):
    """Show comic details and issues."""
    comic_url = f"{scraper.base_url}/Comic/{comic_slug}"
    
    try:
        info = scraper.get_comic_info(comic_url)
        issues = scraper.get_issues(comic_url)
        
        return render_template('comic.html', 
                             comic_url=comic_url,
                             comic_slug=comic_slug,
                             info=info, 
                             issues=issues)
    except Exception as e:
        return f"Error loading comic: {e}", 500

@app.route('/api/comic/info', methods=['POST'])
def get_comic_info():
    """API endpoint to get comic info."""
    comic_url = request.json.get('url', '')
    if not comic_url:
        return jsonify({'error': 'No comic URL provided'}), 400
    
    try:
        info = scraper.get_comic_info(comic_url)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/comic/issues', methods=['POST'])
def get_issues():
    """API endpoint to get comic issues."""
    comic_url = request.json.get('url', '')
    if not comic_url:
        return jsonify({'error': 'No comic URL provided'}), 400
    
    try:
        issues = scraper.get_issues(comic_url)
        return jsonify({'issues': issues})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/issue/images', methods=['POST'])
def get_issue_images():
    """API endpoint to get issue image URLs."""
    issue_url = request.json.get('url', '')
    if not issue_url:
        return jsonify({'error': 'No issue URL provided'}), 400
    
    try:
        image_urls = scraper.get_issue_image_urls(issue_url)
        return jsonify({'images': image_urls})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_issue():
    """API endpoint to download an issue."""
    issue = request.json.get('issue')
    output_dir = request.json.get('output_dir', 'downloads')
    
    if not issue:
        return jsonify({'error': 'No issue provided'}), 400
    
    try:
        issue_dir = scraper.download_issue(issue, output_dir=output_dir)
        return jsonify({'success': True, 'path': issue_dir})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.teardown_appcontext
def cleanup(exception=None):
    """Clean up resources on app shutdown."""
    pass  # scraper persists across requests

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='readcomics-cli web interface')
    parser.add_argument('-p', '--port', type=int, default=5000, 
                       help='Port to run the server on (default: 5000)')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                       help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--debug', action='store_true',
                       help='Run in debug mode')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("readcomics-cli Web Interface")
    print("=" * 60)
    print(f"Starting server at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    try:
        app.run(host=args.host, port=args.port, debug=args.debug)
    finally:
        scraper.close()
