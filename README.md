# NN/g Study Guide PDF Downloader & Verifier

A desktop-gui and command-line automation tool to download entire study guides from the **Nielsen Norman Group (NN/g)** website, saving all articles and embedded video transcripts as neatly numbered, formatted PDF files.

---

## Features

1. **Desktop GUI Application (`app.py`)**:
   * **Clean Dark Theme**: Beautiful modern flat-design layout.
   * **Custom Save Folder**: Browse and select or create any directory on your computer.
   * **Real-time Terminal Log**: Stream execution logs line-by-line directly inside the GUI.
   * **Multi-Threaded Execution**: Runs crawling, verification, and retries in background threads to keep the UI fully responsive.
   * **Quick Launch bat (`run_gui.bat`)**: Double-click to launch the GUI without bringing up a command prompt window.

2. **Advanced Scraping & Rendering (`crawler.py`)**:
   * **Auto-Numbering**: Prepend `XX. ` to topic folders and `YY. ` to PDF filenames in their exact sequence from the NN/g guide.
   * **Embedded Video Support**: Detects and extracts YouTube videos (bypassing CookieYes consent banners).
   * **YouTube Transcript PDF**: Downloads YouTube subtitles and renders them as a print-ready PDF.
   * **Robust Fallback**: Automatically prints the original NN/g video article description to PDF if the YouTube API is rate-limited or blocked.
   * **CLI Parameter Support**: Allows custom URLs and output directories from the terminal.

3. **Validation & Smart-Retry (`verify_downloads.py`)**:
   * **PDF Health Check**: Opens PDFs using `pypdf` to verify page counts and check for corruption.
   * **Smart Classification**: Detects which files have subtitles vs. those that fell back.
   * **Prefix-Based Matching**: Avoids filename mismatches caused by curly quotes or special characters.
   * **Smart-Retry**: Running with `--retry` downloads *only* the missing or fallback files.

---

## Installation

### Prerequisites
Make sure you have [Python 3.x](https://www.python.org/downloads/) installed.

### 1. Clone the repository
```bash
git clone https://github.com/quendinao/NNgroup-articles-crawler.git
cd NNgroup-articles-crawler
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Install Playwright browser binaries
```bash
playwright install chromium
```

---

## Usage

### Option 1: Using the Desktop GUI (Recommended)
Double-click the **`run_gui.bat`** file inside the project directory, or launch it from the terminal:
```bash
python app.py
```
* **Enter URL**: Paste any NN/g Study Guide URL (e.g. `https://www.nngroup.com/articles/psychology-study-guide/`).
* **Choose folder**: Click **Browse...** to select your target folder.
* **Click Buttons**:
  * **Start Crawl**: Clean and download all items.
  * **Verify Downloads**: Audit files for health and completeness.
  * **Smart Retry**: Redownload failed/fallback items (ideal after changing VPN/IP to bypass YouTube blocks).

### Option 2: Using the Command Line (CLI)

#### 1. Download a guide:
```bash
python crawler.py [STUDY_GUIDE_URL] [SAVING_DIRECTORY]
```
*(Default: Psychology Study Guide saved to `./psychology_articles/`)*

#### 2. Verify downloaded PDFs:
```bash
python verify_downloads.py [STUDY_GUIDE_URL] --output-dir [SAVING_DIRECTORY]
```

#### 3. Smart-retry only missing or fallback files:
```bash
python verify_downloads.py [STUDY_GUIDE_URL] --output-dir [SAVING_DIRECTORY] --retry
```

---

## Technologies Used
* **UI**: Python Tkinter & TTK Styles
* **Parsing**: BeautifulSoup4 (BS4) & urllib
* **Rendering**: Playwright (Headless Chromium)
* **Subtitles**: youtube-transcript-api
* **Verification**: pypdf

---

## License
MIT License. Feel free to modify and adapt!
