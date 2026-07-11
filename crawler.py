import os
import re
import sys
import time
import urllib.request
import urllib.parse as urlparse
import shutil
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
import asyncio
from playwright.async_api import async_playwright

ROOT_URL = "https://www.nngroup.com/articles/psychology-study-guide/"
OUTPUT_DIR = "psychology_articles"
REPORT_FILE = "download_report.txt"

# Selectors to clean up before printing
CLEANUP_SELECTORS = [
    'header', 'footer', '.global-nav', '.banner-sales', 
    '.article-share', '.article-sidebar', '.related-content.related-articles',
    '.sidebar-wrapper', '#cookie-preferences', '.cky-consent-container',
    '.cookie-button', '.related-courses', '.related-topics', '.article-videos',
    'aside', '.learn-more-title', '.related-articles-title', '.ds-wrapper.header-content',
    '.nav-main', '.footer', '.banner-sales__content', '.newsletter-signup', '.author-bio',
    '#nav-global', '#footer-global', '.page-header', '.page-footer'
]

# Style overrides to force full-width layout for articles
LAYOUT_OVERRIDE_CSS = """
body { 
    margin: 0 !important; 
    padding: 20px !important; 
    width: 100% !important; 
    max-width: 100% !important;
}
.article-container { 
    display: block !important; 
    width: 100% !important; 
    max-width: 100% !important; 
    grid-template-columns: none !important; 
    margin: 0 !important;
    padding: 0 !important;
}
.article-content { 
    width: 100% !important; 
    max-width: 100% !important; 
    margin: 0 !important;
    padding: 0 !important;
}
.article-body { 
    width: 100% !important; 
    max-width: 100% !important; 
    margin: 0 !important;
    padding: 0 !important;
}
"""

def sanitize_filename(name):
    # Remove invalid characters for Windows folder and file names
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = name.strip()
    return name[:120]  # Limit length to avoid path length issues

def get_youtube_video_id(url):
    parsed_url = urlparse.urlparse(url)
    if parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            p = urlparse.parse_qs(parsed_url.query)
            return p.get('v', [None])[0]
        if parsed_url.path.startswith(('/embed/', '/v/')):
            return parsed_url.path.split('/')[2]
    return None

def fetch_youtube_transcript(video_id):
    """Fetch transcript, trying with cookies first, then without if that fails."""
    import requests

    def _try_fetch(use_cookies):
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        })

        if use_cookies:
            cookies_file = None
            for name in ["youtube_cookies.txt", "cookies.txt"]:
                p = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
                if os.path.exists(p):
                    cookies_file = p
                    break
            if cookies_file:
                print(f"  [YouTube API] Using cookies from: {os.path.basename(cookies_file)}")
                from http.cookiejar import MozillaCookieJar
                try:
                    cj = MozillaCookieJar(cookies_file)
                    cj.load(ignore_discard=True, ignore_expires=True)
                    session.cookies = cj
                except Exception as cookie_err:
                    print(f"  [Warning] Failed to load cookies file ({cookie_err}).")
            else:
                use_cookies = False  # No file found, skip

        api = YouTubeTranscriptApi(http_client=session)
        transcript_list = api.list(video_id)
        try:
            transcript = transcript_list.find_transcript(['vi'])
        except Exception:
            try:
                transcript = transcript_list.find_transcript(['en'])
            except Exception:
                transcript = next(iter(transcript_list))
        data = transcript.fetch()
        return data, transcript.language

    # Attempt 1: with cookies
    try:
        return _try_fetch(use_cookies=True)
    except Exception as e1:
        print(f"  [YouTube API] Error fetching transcript for {video_id}: {e1}")
        # Attempt 2: retry WITHOUT cookies (cookies themselves can trigger blocks)
        print(f"  [YouTube API] Retrying WITHOUT cookies for {video_id}...")
        try:
            return _try_fetch(use_cookies=False)
        except Exception as e2:
            print(f"  [YouTube API] Retry also failed for {video_id}: {e2}")
            return None, None

def get_youtube_video_title(video_id):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            match = re.search(r'<title>(.*?)</title>', html)
            if match:
                title = match.group(1).replace(" - YouTube", "").strip()
                return title
    except Exception:
        pass
    return None

def format_transcript_as_html(title, video_url, transcript_data, language):
    html_lines = []
    html_lines.append("<!DOCTYPE html>")
    html_lines.append("<html><head><meta charset='UTF-8'>")
    html_lines.append(f"<title>[Video Transcript] {title}</title>")
    html_lines.append("<style>")
    html_lines.append("body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; margin: 40px; color: #333; }")
    html_lines.append("h1 { color: #FF3921; border-bottom: 2px solid #FF3921; padding-bottom: 10px; }")
    html_lines.append(".meta { color: #666; margin-bottom: 30px; font-style: italic; }")
    html_lines.append(".transcript-entry { margin-bottom: 15px; display: flex; }")
    html_lines.append(".timestamp { font-weight: bold; color: #FF3921; min-width: 80px; }")
    html_lines.append(".text { flex-grow: 1; }")
    html_lines.append("</style></head><body>")
    html_lines.append(f"<h1>[Video Transcript] {title}</h1>")
    html_lines.append(f"<div class='meta'>Original Video: <a href='{video_url}' target='_blank'>{video_url}</a> | Language: {language}</div>")
    
    if transcript_data:
        for entry in transcript_data:
            start_time = entry.start
            minutes = int(start_time // 60)
            seconds = int(start_time % 60)
            timestamp_str = f"{minutes:02d}:{seconds:02d}"
            text = entry.text
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_lines.append(f"<div class='transcript-entry'><span class='timestamp'>[{timestamp_str}]</span><span class='text'>{text}</span></div>")
    else:
        html_lines.append("<p>No transcript available or could not be loaded.</p>")
        
    html_lines.append("</body></html>")
    return "\n".join(html_lines)

def parse_root_guide(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    article_body = soup.find('div', class_='article-body')
    if not article_body:
        article_body = soup.find('article')
    
    if not article_body:
        print("[Error] Could not find article body in root page.")
        return {}
    
    topics = {}
    current_topic = None
    
    # Pre-order DFS traversal of descendants to find headers and lists of links
    for elem in article_body.descendants:
        if elem.name == 'h2':
            topic_name = elem.get_text().strip()
            # Ignore non-topic H2 sections
            if topic_name in [
                "Additional Paid Resources", "Related Courses", "Related Topics", 
                "Learn More:", "Related Articles:", "Never miss an update", 
                "Follow Us", "References", "Study Guide"
            ]:
                current_topic = None
                continue
            current_topic = topic_name
            topics[current_topic] = []
        elif elem.name == 'a' and current_topic:
            href = elem.get('href', '')
            text = elem.get_text().strip()
            if href and text:
                full_url = href if href.startswith('http') else 'https://www.nngroup.com' + href
                # Match internal article links, video links, or youtube links, ignore comment/utility links
                if ('/articles/' in full_url or '/videos/' in full_url or 'youtube.com' in full_url or 'youtu.be' in full_url) and not full_url.endswith('#comments'):
                    topics[current_topic].append({'title': text, 'url': full_url})
    
    # Filter empty sections
    return {k: v for k, v in topics.items() if v}

async def run_crawler(root_url=None, output_dir=None, no_fallback=False):
    if root_url is None:
        root_url = ROOT_URL
    if output_dir is None:
        output_dir = OUTPUT_DIR
        
    print("==================================================")
    print("Starting UX Psychology Articles Crawler")
    print(f"Root URL: {root_url}")
    print(f"Output Dir: {output_dir}")
    print("==================================================")
    
    # 1. Fetch root page
    print("Fetching study guide page...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        req = urllib.request.Request(root_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8')
    except Exception as e:
        print(f"[Error] Failed to fetch root guide page: {e}")
        return
    
    # 2. Parse topics and links
    study_guide = parse_root_guide(html)
    if not study_guide:
        print("[Error] No topics or links found in root page.")
        return
    
    print(f"Found {len(study_guide)} topics:")
    total_articles = 0
    for topic, links in study_guide.items():
        print(f" - {topic} ({len(links)} links)")
        total_articles += len(links)
    print(f"Total articles to download: {total_articles}")
    
    # Clean and recreate base output directory
    if os.path.exists(output_dir):
        print(f"Cleaning up existing output directory '{output_dir}'...")
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    success_downloads = []
    failed_downloads = []
    
    # 3. Setup Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Set large viewport
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        page = await context.new_page()
        
        # Navigate through each topic and article (numbered)
        for topic_idx, (topic, links) in enumerate(study_guide.items(), 1):
            print(f"\nProcessing section: {topic}")
            folder_name = f"{topic_idx:02d}. {sanitize_filename(topic)}"
            topic_dir = os.path.join(output_dir, folder_name)
            os.makedirs(topic_dir, exist_ok=True)
            
            for index, article in enumerate(links, 1):
                url = article['url']
                link_title = article['title']
                print(f" [{index}/{len(links)}] Scraping: '{link_title}'")
                print(f"  URL: {url}")
                
                try:
                    # Check if link is a YouTube video directly
                    video_id = get_youtube_video_id(url)
                    
                    if video_id:
                        print("  [Type: YouTube] Direct YouTube video link detected.")
                        # Fetch title from YouTube if possible, otherwise use anchor text
                        yt_title = get_youtube_video_title(video_id) or link_title
                        safe_title = f"{index:02d}. " + sanitize_filename(f"[Video] {yt_title}")
                        pdf_path = os.path.join(topic_dir, f"{safe_title}.pdf")
                        
                        # Get subtitles
                        transcript_data, lang = fetch_youtube_transcript(video_id)
                        if transcript_data:
                            html_content = format_transcript_as_html(yt_title, url, transcript_data, lang)
                            await page.set_content(html_content)
                            await page.pdf(
                                path=pdf_path, 
                                format="A4", 
                                margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
                                print_background=True
                            )
                            print(f"  [Success] Saved transcript PDF to: {pdf_path}")
                            success_downloads.append({'title': link_title, 'url': url, 'section': topic, 'type': 'YouTube Video Transcript'})
                        else:
                            raise Exception("Failed to fetch YouTube subtitles/transcript")
                            
                    else:
                        # Normal NN/g article page
                        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                        
                        # Wait for page body to load
                        await page.wait_for_timeout(2000)
                        
                        # Check if the page contains a YouTube iframe (in src, data-cookieblock-src, or data-src)
                        embed_video_url = await page.evaluate("""() => {
                            const iframes = Array.from(document.querySelectorAll('iframe'));
                            for (const iframe of iframes) {
                                const src = iframe.getAttribute('src') || '';
                                const dataSrc = iframe.getAttribute('data-cookieblock-src') || iframe.getAttribute('data-src') || '';
                                if (src.includes('youtube.com') || src.includes('youtu.be')) return src;
                                if (dataSrc.includes('youtube.com') || dataSrc.includes('youtu.be')) return dataSrc;
                            }
                            return null;
                        }""")
                        
                        has_yt_embed = embed_video_url is not None
                        article_text_len = 0
                        
                        if has_yt_embed:
                            # Evaluate text length in article body
                            article_text_len = await page.evaluate("""() => {
                                const body = document.querySelector('.article-body') || document.querySelector('article');
                                return body ? body.innerText.length : 0;
                            }""")
                        
                        # If it is a video page (either has /videos/ in url, or mainly a video with less than 900 chars description)
                        is_video_page = ('/videos/' in url) or (has_yt_embed and article_text_len < 900)
                        
                        if is_video_page and has_yt_embed:
                            print(f"  [Type: NN/g Video Page] Embedded video page detected: {url}")
                            embed_video_id = get_youtube_video_id(embed_video_url)
                            
                            if embed_video_id:
                                # Get title from H1 or document title
                                page_title = await page.evaluate("() => (document.querySelector('h1.article-h1') || document.querySelector('h1') || {}).innerText || document.title")
                                page_title = page_title.replace(" - NN/g", "").strip()
                                if not page_title:
                                    page_title = link_title
                                
                                safe_title = f"{index:02d}. " + sanitize_filename(f"[Video] {page_title}")
                                pdf_path = os.path.join(topic_dir, f"{safe_title}.pdf")
                                
                                print(f"  Fetching YouTube transcript for video ID: {embed_video_id}")
                                transcript_data, lang = fetch_youtube_transcript(embed_video_id)
                                if transcript_data:
                                    html_content = format_transcript_as_html(page_title, embed_video_url, transcript_data, lang)
                                    await page.set_content(html_content)
                                    await page.pdf(
                                        path=pdf_path, 
                                        format="A4", 
                                        margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
                                        print_background=True
                                    )
                                    print(f"  [Success] Saved embedded video transcript PDF to: {pdf_path}")
                                    success_downloads.append({'title': link_title, 'url': url, 'section': topic, 'type': 'Embedded Video Transcript'})
                                    continue
                                else:
                                    if no_fallback:
                                        raise Exception("Failed to fetch YouTube subtitles/transcript (no-fallback enabled)")
                                    print("  [Warning] Subtitle fetch failed, falling back to standard page print.")
                        
                        # Process as a standard article
                        # Extract title from h1
                        page_title = await page.evaluate("() => (document.querySelector('h1.article-h1') || document.querySelector('h1') || {}).innerText || document.title")
                        page_title = page_title.replace(" - NN/g", "").strip()
                        if not page_title:
                            page_title = link_title
                            
                        safe_title = f"{index:02d}. " + sanitize_filename(page_title)
                        pdf_path = os.path.join(topic_dir, f"{safe_title}.pdf")
                        
                        # Scroll page to bottom to trigger lazy-loaded images
                        print("  Scrolling page to trigger lazy load...")
                        await page.evaluate("""
                            async () => {
                                await new Promise((resolve) => {
                                    let totalHeight = 0;
                                    const distance = 400;
                                    const timer = setInterval(() => {
                                        const scrollHeight = document.body.scrollHeight;
                                        window.scrollBy(0, distance);
                                        totalHeight += distance;
                                        if (totalHeight >= scrollHeight) {
                                            clearInterval(timer);
                                            window.scrollTo(0, 0);
                                            resolve();
                                        }
                                    }, 50);
                                });
                            }
                        """)
                        await page.wait_for_timeout(1000)
                        
                        # Clean up page layout and elements
                        selectors_json = ",".join([f"'{s}'" for s in CLEANUP_SELECTORS])
                        await page.evaluate(f"""() => {{
                            const selectors = [{selectors_json}];
                            selectors.forEach(sel => {{
                                document.querySelectorAll(sel).forEach(el => el.remove());
                            }});
                            
                            // Inject CSS override
                            const style = document.createElement('style');
                            style.innerHTML = `{LAYOUT_OVERRIDE_CSS}`;
                            document.head.appendChild(style);
                        }}""")
                        
                        # Generate PDF
                        await page.pdf(
                            path=pdf_path, 
                            format="A4", 
                            margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
                            print_background=True
                        )
                        print(f"  [Success] Saved PDF to: {pdf_path}")
                        success_downloads.append({'title': page_title, 'url': url, 'section': topic, 'type': 'Article PDF'})
                        
                except Exception as e:
                    print(f"  [Error] Failed to process '{link_title}': {e}")
                    failed_downloads.append({
                        'title': link_title,
                        'url': url,
                        'section': topic,
                        'error': str(e)
                    })
                
                # Moderate delay to prevent rate limit blocks
                await asyncio.sleep(1.5)
                
        await browser.close()
        
    # Write report
    write_report(success_downloads, failed_downloads)

def write_report(successes, failures):
    report_lines = []
    report_lines.append("==================================================")
    report_lines.append("DOWNLOAD REPORT - UX PSYCHOLOGY ARTICLES CRAWLER")
    report_lines.append(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("==================================================")
    report_lines.append(f"Total articles found: {len(successes) + len(failures)}")
    report_lines.append(f"Successfully downloaded: {len(successes)}")
    report_lines.append(f"Failed downloads: {len(failures)}")
    report_lines.append("")
    
    if failures:
        report_lines.append("FAILED DOWNLOADS DETAILS:")
        report_lines.append("--------------------------------------------------")
        for f in failures:
            report_lines.append(f"Section: {f['section']}")
            report_lines.append(f"Article: {f['title']}")
            report_lines.append(f"URL:     {f['url']}")
            report_lines.append(f"Error:   {f['error']}")
            report_lines.append("--------------------------------------------------")
    else:
        report_lines.append("All articles downloaded successfully with zero failures!")
        
    report_lines.append("")
    report_lines.append("SUCCESSFUL DOWNLOADS LIST:")
    report_lines.append("--------------------------------------------------")
    for s in successes:
        report_lines.append(f"[{s['section']}] ({s['type']}) {s['title']} -> {s['url']}")
        
    report_content = "\n".join(report_lines)
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print("\n==================================================")
    print("CRAWLING COMPLETED")
    print(f"Successful: {len(successes)} | Failed: {len(failures)}")
    print(f"Detailed report saved to: {os.path.abspath(REPORT_FILE)}")
    if failures:
        print("\n!!! WARNING: Some downloads failed. Please review the failed list:")
        for idx, f in enumerate(failures, 1):
            print(f"  {idx}. Section: '{f['section']}' | Article: '{f['title']}' | Error: {f['error']}")
    print("==================================================")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="UX Psychology Articles Crawler")
    parser.add_argument("url", nargs="?", default=ROOT_URL, help="The study guide URL to crawl.")
    parser.add_argument("output_dir", nargs="?", default=OUTPUT_DIR, help="The directory to save PDFs.")
    parser.add_argument("--no-fallback", action="store_true", help="Do not fall back to standard page print if transcript fails.")
    args = parser.parse_args()
    
    asyncio.run(run_crawler(args.url, args.output_dir, no_fallback=args.no_fallback))
