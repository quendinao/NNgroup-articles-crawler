import os
import sys
import urllib.request
import argparse
from pypdf import PdfReader
from bs4 import BeautifulSoup
import asyncio

# Add workspace directory to python path just in case
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import functions and constants from crawler.py
from crawler import (
    ROOT_URL, OUTPUT_DIR, parse_root_guide, sanitize_filename,
    get_youtube_video_id, fetch_youtube_transcript, get_youtube_video_title,
    format_transcript_as_html, CLEANUP_SELECTORS, LAYOUT_OVERRIDE_CSS
)
from playwright.async_api import async_playwright

VERIFICATION_REPORT = "verification_report.txt"

def verify_pdf(file_path):
    """
    Verifies the PDF file using pypdf.
    Returns (is_valid, is_corrupted, page_count, first_page_text)
    """
    if not os.path.exists(file_path):
        return False, False, 0, ""
    
    if os.path.getsize(file_path) == 0:
        return True, True, 0, "" # Empty file is corrupted
        
    try:
        reader = PdfReader(file_path)
        page_count = len(reader.pages)
        if page_count == 0:
            return True, True, 0, ""
        
        # Extract text from the first page
        first_page_text = ""
        try:
            first_page_text = reader.pages[0].extract_text() or ""
        except Exception:
            pass
            
        return True, False, page_count, first_page_text
    except Exception:
        return True, True, 0, ""

async def retry_downloads(items_to_retry):
    """
    Downloads only the missing, corrupted, or fallback files.
    """
    if not items_to_retry:
        print("\nNo items need to be redownloaded.")
        return
        
    print(f"\n==================================================")
    print(f"Retrying download for {len(items_to_retry)} items...")
    print(f"Please ensure your VPN or IP is changed if YouTube was blocking you.")
    print(f"==================================================")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        page = await context.new_page()
        
        for idx, item in enumerate(items_to_retry, 1):
            url = item['url']
            link_title = item['title']
            topic_dir = item['topic_dir']
            filename = item['filename']
            pdf_path = os.path.join(topic_dir, filename)
            
            print(f"\n [{idx}/{len(items_to_retry)}] Redownloading: '{link_title}'")
            print(f"  URL: {url}")
            print(f"  Path: {pdf_path}")
            
            try:
                # Remove the old file if it exists
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                    
                video_id = get_youtube_video_id(url)
                
                if video_id:
                    print("  [Type: YouTube] Fetching transcript...")
                    yt_title = get_youtube_video_title(video_id) or link_title
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
                    else:
                        raise Exception("Failed to fetch YouTube subtitles/transcript")
                else:
                    # Normal NN/g page or video-only page
                    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)
                    
                    # Check YouTube iframe
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
                        article_text_len = await page.evaluate("""() => {
                            const body = document.querySelector('.article-body') || document.querySelector('article');
                            return body ? body.innerText.length : 0;
                        }""")
                        
                    is_video_page = ('/videos/' in url) or (has_yt_embed and article_text_len < 900)
                    
                    if is_video_page and has_yt_embed:
                        print(f"  [Type: NN/g Video Page] Fetching transcript...")
                        embed_video_id = get_youtube_video_id(embed_video_url)
                        if embed_video_id:
                            page_title = await page.evaluate("() => (document.querySelector('h1.article-h1') || document.querySelector('h1') || {}).innerText || document.title")
                            page_title = page_title.replace(" - NN/g", "").strip() or link_title
                            
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
                                continue
                            else:
                                print("  [Warning] Subtitle fetch failed, falling back to standard page print.")
                                
                    # Standard page print
                    page_title = await page.evaluate("() => (document.querySelector('h1.article-h1') || document.querySelector('h1') || {}).innerText || document.title")
                    page_title = page_title.replace(" - NN/g", "").strip() or link_title
                    
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
                    
                    selectors_json = ",".join([f"'{s}'" for s in CLEANUP_SELECTORS])
                    await page.evaluate(f"""() => {{
                        const selectors = [{selectors_json}];
                        selectors.forEach(sel => {{
                            document.querySelectorAll(sel).forEach(el => el.remove());
                        }});
                        const style = document.createElement('style');
                        style.innerHTML = `{LAYOUT_OVERRIDE_CSS}`;
                        document.head.appendChild(style);
                    }}""")
                    
                    await page.pdf(
                        path=pdf_path, 
                        format="A4", 
                        margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
                        print_background=True
                    )
                    print(f"  [Success] Redownloaded standard PDF to: {pdf_path}")
                    
            except Exception as e:
                print(f"  [Error] Failed to redownload '{link_title}': {e}")
            
            await asyncio.sleep(1.5)
            
        await browser.close()

def main():
    parser = argparse.ArgumentParser(description="Verify UX Psychology PDF downloads.")
    parser.add_argument("url", nargs="?", default=ROOT_URL, help="The study guide URL to verify.")
    parser.add_argument("--output-dir", default=OUTPUT_DIR, help="The directory to save/verify files.")
    parser.add_argument("--retry", action="store_true", help="Redownload failed or fallback files.")
    args = parser.parse_args()
    
    target_url = args.url
    output_dir = args.output_dir
    
    print("==================================================")
    print("Starting PDF Download Verification")
    print(f"URL: {target_url}")
    print(f"Output Dir: {output_dir}")
    print("==================================================")
    
    # 1. Fetch root page to get ground truth list
    print("Fetching study guide page to get ground truth list...")
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    try:
        req = urllib.request.Request(target_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8')
    except Exception as e:
        print(f"[Error] Failed to fetch root guide page: {e}")
        return
        
    study_guide = parse_root_guide(html)
    if not study_guide:
        print("[Error] No topics or links found in root page.")
        return
        
    print(f"Ground truth loaded. Checking files inside '{output_dir}'...")
    
    missing_files = []
    corrupted_files = []
    fallback_videos = []
    success_articles = []
    success_video_transcripts = []
    
    # Track items for potential smart retry
    retry_list = []
    
    for topic_idx, (topic, links) in enumerate(study_guide.items(), 1):
        folder_name = f"{topic_idx:02d}. {sanitize_filename(topic)}"
        topic_dir = os.path.join(output_dir, folder_name)
        
        for index, article in enumerate(links, 1):
            url = article['url']
            link_title = article['title']
            
            # Determine expected filename
            video_id = get_youtube_video_id(url)
            is_video_link = ('/videos/' in url) or (video_id is not None)
            
            # We check both possible filenames (with/without [Video] tag)
            # Find which file exists in the topic directory by checking the index prefix
            file_exists = False
            chosen_filename = f"{index:02d}. {sanitize_filename(link_title)}.pdf"  # Fallback expected name
            prefix = f"{index:02d}. "
            
            if os.path.exists(topic_dir):
                for fn in os.listdir(topic_dir):
                    if fn.startswith(prefix) and fn.endswith(".pdf"):
                        file_exists = True
                        chosen_filename = fn
                        break
                        
            pdf_path = os.path.join(topic_dir, chosen_filename)
            
            item_info = {
                'title': link_title,
                'url': url,
                'section': topic,
                'topic_dir': topic_dir,
                'filename': chosen_filename,
                'path': pdf_path
            }
            
            if not file_exists:
                missing_files.append(item_info)
                retry_list.append(item_info)
                continue
                
            # Verify file integrity
            exists, is_corrupted, page_count, first_page_text = verify_pdf(pdf_path)
            
            if is_corrupted:
                item_info['error'] = "File corrupted or 0 pages"
                corrupted_files.append(item_info)
                retry_list.append(item_info)
                continue
                
            # Verify if video page has transcript or is fallback
            if is_video_link:
                # If it's a video, check if it contains the transcript indicator
                # We injected "Video Transcript" or "Original Video:" in the HTML
                is_transcript = "[Video Transcript]" in first_page_text or "Original Video:" in first_page_text
                
                if not is_transcript:
                    item_info['error'] = "Video saved as fallback article layout (no transcript found)"
                    fallback_videos.append(item_info)
                    retry_list.append(item_info)
                else:
                    success_video_transcripts.append(item_info)
            else:
                success_articles.append(item_info)
                
    # 3. Print Report
    report = []
    report.append("==================================================")
    report.append("VERIFICATION REPORT - UX PSYCHOLOGY DOWNLOADS")
    report.append("==================================================")
    report.append(f"Total links checked: {sum(len(l) for l in study_guide.values())}")
    report.append(f" - Successfully verified Articles: {len(success_articles)}")
    report.append(f" - Successfully verified Video Transcripts: {len(success_video_transcripts)}")
    report.append(f" - Missing files: {len(missing_files)}")
    report.append(f" - Corrupted/Empty files: {len(corrupted_files)}")
    report.append(f" - Fallback Video pages (no transcripts): {len(fallback_videos)}")
    report.append("")
    
    if missing_files:
        report.append("MISSING FILES:")
        for idx, f in enumerate(missing_files, 1):
            report.append(f"  {idx}. [{f['section']}] {f['filename']} (URL: {f['url']})")
        report.append("")
        
    if corrupted_files:
        report.append("CORRUPTED/EMPTY FILES:")
        for idx, f in enumerate(corrupted_files, 1):
            report.append(f"  {idx}. [{f['section']}] {f['filename']} (Error: {f['error']})")
        report.append("")
        
    if fallback_videos:
        report.append("FALLBACK VIDEO PAGES (No transcript available, saved as normal page):")
        for idx, f in enumerate(fallback_videos, 1):
            report.append(f"  {idx}. [{f['section']}] {f['filename']} (URL: {f['url']})")
        report.append("")
        
    report_text = "\n".join(report)
    print(report_text)
    
    with open(VERIFICATION_REPORT, "w", encoding="utf-8") as f:
        f.write(report_text)
        
    print(f"Detailed verification report saved to: {os.path.abspath(VERIFICATION_REPORT)}")
    
    if retry_list:
        if args.retry:
            asyncio.run(retry_downloads(retry_list))
            # Run verification once more to confirm
            print("\nRe-verifying files after retrying...")
            main_reverify(target_url, output_dir)
        else:
            print("\n==================================================")
            print(f"NOTE: There are {len(retry_list)} files that are missing, corrupted, or saved as fallback.")
            print("To attempt redownloading them, run:")
            print(f"  python verify_downloads.py \"{target_url}\" --output-dir \"{output_dir}\" --retry")
            print("==================================================")
    else:
        print("\n==================================================")
        print("ALL DOWNLOADS PERFECTLY RETRIEVED AND VERIFIED!")
        print("==================================================")

def main_reverify(url, output_dir):
    # Helper to run verification with URL and output dir to show final status after retry
    import subprocess
    subprocess.run(["python", "verify_downloads.py", url, "--output-dir", output_dir])

if __name__ == "__main__":
    main()
