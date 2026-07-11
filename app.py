import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import subprocess
import asyncio
from playwright.async_api import async_playwright

# Theme Colors (Catppuccin Mocha-inspired premium dark theme)
BG_COLOR = "#1e1e2e"          # Dark base
CARD_BG = "#252538"           # Card container background
TEXT_COLOR = "#cdd6f4"        # Main text
ACCENT_BLUE = "#89b4fa"       # Flat blue button / highlight
ACCENT_GREEN = "#a6e3a1"      # Terminal green / success
ACCENT_RED = "#f38ba8"        # Error text
BORDER_COLOR = "#45475a"      # Outline / border
CONSOLE_BG = "#11111b"        # Deep black terminal background

DEFAULT_URL = "https://www.nngroup.com/articles/psychology-study-guide/"
DEFAULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "psychology_articles")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("NN/g Study Guide PDF Downloader & Verifier")
        self.geometry("900x700")
        self.configure(bg=BG_COLOR)
        
        # Keep track of running subprocess
        self.active_process = None
        self.is_running = False
        
        # Main layout configuration
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.create_styles()
        self.create_widgets()
        self.update_cookies_status()
        
    def create_styles(self):
        # Configure overall ttk styles to look flat and modern
        self.style = ttk.Style()
        self.style.theme_use('default')
        
        # Configure frames
        self.style.configure('TFrame', background=BG_COLOR)
        self.style.configure('Card.TFrame', background=CARD_BG, relief="flat")
        
        # Configure labels
        self.style.configure('TLabel', background=BG_COLOR, foreground=TEXT_COLOR, font=("Segoe UI", 10))
        self.style.configure('Title.TLabel', background=BG_COLOR, foreground=ACCENT_BLUE, font=("Segoe UI Semibold", 18))
        self.style.configure('CardLabel.TLabel', background=CARD_BG, foreground=TEXT_COLOR, font=("Segoe UI Semibold", 10))
        self.style.configure('Status.TLabel', background=BG_COLOR, foreground=ACCENT_GREEN, font=("Segoe UI Italic", 10))
        
    def create_widgets(self):
        # --- 1. HEADER SECTION ---
        header_frame = ttk.Frame(self, style='TFrame')
        header_frame.grid(row=0, column=0, sticky="ew", padx=25, pady=(20, 10))
        header_frame.columnconfigure(0, weight=1)
        
        title_label = ttk.Label(header_frame, text="NN/g Study Guide Downloader & Verifier", style='Title.TLabel')
        title_label.grid(row=0, column=0, sticky="w")
        
        self.status_label = ttk.Label(header_frame, text="Status: Ready", style='Status.TLabel')
        self.status_label.grid(row=0, column=1, sticky="e")
        
        # --- 2. INPUTS CARD SECTION ---
        inputs_card = ttk.Frame(self, style='Card.TFrame')
        inputs_card.grid(row=1, column=0, sticky="ew", padx=25, pady=10)
        inputs_card.columnconfigure(1, weight=1)
        
        # Internal padding inside the card
        pad_x, pad_y = 15, 10
        
        # URL Input Row
        url_label = ttk.Label(inputs_card, text="Study Guide URL:", style='CardLabel.TLabel')
        url_label.grid(row=0, column=0, sticky="w", padx=(pad_x, 10), pady=pad_y)
        
        self.url_var = tk.StringVar(value=DEFAULT_URL)
        self.url_entry = tk.Entry(
            inputs_card, 
            textvariable=self.url_var, 
            bg="#313244", 
            fg=TEXT_COLOR, 
            insertbackground=TEXT_COLOR,
            bd=0, 
            highlightthickness=1, 
            highlightbackground=BORDER_COLOR, 
            highlightcolor=ACCENT_BLUE,
            font=("Segoe UI", 10)
        )
        self.url_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(0, pad_x), pady=pad_y)
        
        # Output Directory Input Row
        dir_label = ttk.Label(inputs_card, text="Save Directory:", style='CardLabel.TLabel')
        dir_label.grid(row=1, column=0, sticky="w", padx=(pad_x, 10), pady=pad_y)
        
        self.dir_var = tk.StringVar(value=DEFAULT_DIR)
        self.dir_entry = tk.Entry(
            inputs_card, 
            textvariable=self.dir_var, 
            bg="#313244", 
            fg=TEXT_COLOR, 
            insertbackground=TEXT_COLOR,
            bd=0, 
            highlightthickness=1, 
            highlightbackground=BORDER_COLOR, 
            highlightcolor=ACCENT_BLUE,
            font=("Segoe UI", 10)
        )
        self.dir_entry.grid(row=1, column=1, sticky="ew", pady=pad_y)
        
        # Browse Button
        browse_btn = tk.Button(
            inputs_card, 
            text="Browse...", 
            command=self.browse_directory,
            bg=BORDER_COLOR, 
            fg=TEXT_COLOR, 
            bd=0, 
            padx=15, 
            pady=3, 
            relief="flat", 
            activebackground="#585b70", 
            activeforeground=TEXT_COLOR,
            font=("Segoe UI Semibold", 9)
        )
        browse_btn.grid(row=1, column=2, padx=(10, pad_x), pady=pad_y)
        
        # YouTube Session status row
        yt_label = ttk.Label(inputs_card, text="YouTube Cookies:", style='CardLabel.TLabel')
        yt_label.grid(row=2, column=0, sticky="w", padx=(pad_x, 10), pady=pad_y)
        
        self.cookies_status_var = tk.StringVar(value="Checking...")
        self.cookies_status_label = tk.Label(
            inputs_card, 
            textvariable=self.cookies_status_var,
            bg=CARD_BG, 
            fg=ACCENT_RED,
            font=("Segoe UI", 9, "italic"),
            anchor="w"
        )
        self.cookies_status_label.grid(row=2, column=1, columnspan=2, sticky="w", pady=pad_y)
        
        # Chrome Profile row
        profile_label = ttk.Label(inputs_card, text="Chrome Profile:", style='CardLabel.TLabel')
        profile_label.grid(row=3, column=0, sticky="w", padx=(pad_x, 10), pady=pad_y)
        
        # Detect profiles
        self.profile_list = self.detect_chrome_profiles()
        profile_display_names = [p[1] for p in self.profile_list]
        
        self.profile_var = tk.StringVar(value=profile_display_names[0])
        self.profile_combo = ttk.Combobox(
            inputs_card,
            textvariable=self.profile_var,
            values=profile_display_names,
            state="readonly",
            font=("Segoe UI", 9)
        )
        self.profile_combo.grid(row=3, column=1, sticky="ew", pady=pad_y)
        
        # Get Cookies Button
        get_cookies_btn = tk.Button(
            inputs_card, 
            text="Get Cookies", 
            command=self.get_youtube_cookies,
            bg=ACCENT_BLUE, 
            fg="#11111b", 
            bd=0, 
            padx=15, 
            pady=3, 
            relief="flat", 
            activebackground="#74c7ec", 
            activeforeground="#11111b",
            font=("Segoe UI Semibold", 9)
        )
        get_cookies_btn.grid(row=3, column=2, padx=(10, pad_x), pady=pad_y)
        
        # --- 3. CONSOLE OUTPUT PANEL ---
        console_frame = ttk.Frame(self, style='TFrame')
        console_frame.grid(row=2, column=0, sticky="nsew", padx=25, pady=10)
        console_frame.grid_rowconfigure(1, weight=1)
        console_frame.grid_columnconfigure(0, weight=1)
        
        console_label = ttk.Label(console_frame, text="Execution Terminal Output Log:", style='TLabel')
        console_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        self.console = scrolledtext.ScrolledText(
            console_frame, 
            bg=CONSOLE_BG, 
            fg=ACCENT_GREEN, 
            insertbackground=TEXT_COLOR,
            bd=0, 
            highlightthickness=1, 
            highlightbackground=BORDER_COLOR,
            font=("Consolas", 10),
            padx=10, 
            pady=10
        )
        self.console.grid(row=1, column=0, sticky="nsew")
        
        # --- 4. BUTTONS CONTROL BAR ---
        control_bar = ttk.Frame(self, style='TFrame')
        control_bar.grid(row=3, column=0, sticky="ew", padx=25, pady=(10, 20))
        
        # Column weights to spread buttons evenly
        control_bar.grid_columnconfigure(0, weight=1)
        control_bar.grid_columnconfigure(1, weight=1)
        control_bar.grid_columnconfigure(2, weight=1)
        control_bar.grid_columnconfigure(3, weight=1)
        
        # Button 1: Start Crawling
        self.crawl_btn = tk.Button(
            control_bar, 
            text="1. Start Crawl", 
            command=self.trigger_crawl,
            bg=ACCENT_BLUE, 
            fg="#11111b", 
            bd=0, 
            pady=8, 
            relief="flat", 
            activebackground="#74c7ec", 
            activeforeground="#11111b",
            font=("Segoe UI Semibold", 10)
        )
        self.crawl_btn.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        
        # Button 2: Verify PDF Downloads
        self.verify_btn = tk.Button(
            control_bar, 
            text="2. Verify Downloads", 
            command=self.trigger_verify,
            bg=ACCENT_BLUE, 
            fg="#11111b", 
            bd=0, 
            pady=8, 
            relief="flat", 
            activebackground="#74c7ec", 
            activeforeground="#11111b",
            font=("Segoe UI Semibold", 10)
        )
        self.verify_btn.grid(row=0, column=1, padx=5, sticky="ew")
        
        # Button 3: Smart-Retry Failures
        self.retry_btn = tk.Button(
            control_bar, 
            text="3. Smart Retry", 
            command=self.trigger_retry,
            bg=ACCENT_BLUE, 
            fg="#11111b", 
            bd=0, 
            pady=8, 
            relief="flat", 
            activebackground="#74c7ec", 
            activeforeground="#11111b",
            font=("Segoe UI Semibold", 10)
        )
        self.retry_btn.grid(row=0, column=2, padx=5, sticky="ew")
        
        # Button 4: Cancel Execution (Stop subprocess)
        self.cancel_btn = tk.Button(
            control_bar, 
            text="Stop/Cancel", 
            command=self.cancel_execution,
            bg=BORDER_COLOR, 
            fg=TEXT_COLOR, 
            bd=0, 
            pady=8, 
            relief="flat", 
            activebackground=ACCENT_RED, 
            activeforeground="#11111b",
            font=("Segoe UI Semibold", 10)
        )
        self.cancel_btn.grid(row=0, column=3, padx=(10, 0), sticky="ew")
        
        # Disable cancel button by default
        self.cancel_btn.config(state="disabled", bg="#313244", fg="#585b70")
        
    def browse_directory(self):
        selected_dir = filedialog.askdirectory(initialdir=self.dir_var.get())
        if selected_dir:
            self.dir_var.set(os.path.abspath(selected_dir))
            
    def detect_chrome_profiles(self):
        import json
        user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
        local_state_path = os.path.join(user_data_dir, "Local State")
        profiles = []
        
        # Always include Default profile
        profiles.append(("Default", "Default Profile (Default)"))
        
        if os.path.exists(local_state_path):
            try:
                with open(local_state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    info_cache = data.get("profile", {}).get("info_cache", {})
                    for dir_name, info in info_cache.items():
                        friendly_name = info.get("name", dir_name)
                        email = info.get("user_name", "")
                        
                        email_suffix = f" - {email}" if email else ""
                        display_name = f"{friendly_name}{email_suffix} ({dir_name})"
                        
                        if dir_name == "Default":
                            profiles[0] = (dir_name, f"{friendly_name}{email_suffix} (Default)")
                        else:
                            profiles.append((dir_name, display_name))
            except Exception:
                pass
                
        # Insert isolated profile at the top
        profiles.insert(0, (".yt_profile", "Isolated Profile (Clean & Safe)"))
        return profiles

    def update_cookies_status(self):
        cookies_file = None
        for name in ["youtube_cookies.txt", "cookies.txt"]:
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
            if os.path.exists(p):
                cookies_file = p
                break
                
        if cookies_file:
            self.cookies_status_var.set(f"Active ({os.path.basename(cookies_file)})")
            self.cookies_status_label.config(fg=ACCENT_GREEN)
        else:
            self.cookies_status_var.set("Not found (transcripts may fail on rate limit)")
            self.cookies_status_label.config(fg="#a6adc8")

    def get_youtube_cookies(self):
        self.clear_log()
        self.toggle_inputs(False)
        self.set_status("Logging in to YouTube...", True)
        
        # Get selected profile info
        selected_display_name = self.profile_var.get()
        selected_profile_dir = ".yt_profile"
        for dir_name, display_name in self.profile_list:
            if display_name == selected_display_name:
                selected_profile_dir = dir_name
                break
                
        self.append_log("==================================================\n")
        self.append_log("YOUTUBE LOGIN & COOKIES ACQUISITION\n")
        self.append_log("==================================================\n")
        self.append_log(f">>> Profile: {selected_display_name}\n")
        
        if selected_profile_dir != ".yt_profile":
            self.append_log(">>> IMPORTANT: Please close all active Google Chrome windows before proceeding!\n")
        else:
            self.append_log(">>> Opening isolated browser profile...\n")
        
        def work():
            async def task():
                try:
                    async with async_playwright() as p:
                        if selected_profile_dir == ".yt_profile":
                            user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".yt_profile")
                            profile_name = "Default"
                        else:
                            user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
                            profile_name = selected_profile_dir
                        
                        try:
                            if selected_profile_dir == ".yt_profile":
                                context = await p.chromium.launch_persistent_context(
                                    user_data_dir,
                                    channel="chrome",  # Use local Google Chrome installation
                                    headless=False,
                                    viewport={'width': 1280, 'height': 800},
                                    ignore_default_args=["--enable-automation"]
                                )
                            else:
                                context = await p.chromium.launch_persistent_context(
                                    user_data_dir,
                                    profile_name=profile_name,
                                    channel="chrome",  # Use local Google Chrome installation
                                    headless=False,
                                    viewport={'width': 1280, 'height': 800},
                                    ignore_default_args=["--enable-automation"]
                                )
                        except Exception as launch_err:
                            self.append_log(f"\n[Launch Error]: {launch_err}\n")
                            if selected_profile_dir != ".yt_profile":
                                self.append_log("\n[Action Required]: Google Chrome is likely already open with this profile.\n")
                                self.append_log("Please CLOSE all active Google Chrome windows and try again, or use the 'Isolated Profile'.\n")
                                messagebox.showerror(
                                    "Chrome Profile Locked",
                                    f"Cannot open Chrome Profile '{selected_display_name}' because Chrome is currently running.\n\nPlease close all Chrome windows and try again, or select 'Isolated Profile'."
                                )
                            else:
                                self.append_log(">>> Falling back to packaged Chromium binary...\n")
                                context = await p.chromium.launch_persistent_context(
                                    user_data_dir,
                                    headless=False,
                                    viewport={'width': 1280, 'height': 800},
                                    ignore_default_args=["--enable-automation"]
                                )
                            return

                        # Mask webdriver property to bypass Google bot detection
                        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                        page = context.pages[0] if context.pages else await context.new_page()
                        
                        # Handle page flow depending on profile type
                        if selected_profile_dir == ".yt_profile":
                            # Go to Google Accounts login first (sign-in is much more reliable here than direct YouTube)
                            await page.goto("https://accounts.google.com/ServiceLogin")
                            
                            self.append_log("\n[Action Required]:\n")
                            self.append_log("1. Log in to your Google Account in the browser window.\n")
                            self.append_log("2. Once successfully signed in, return to this app and click OK.\n")
                            self.append_log("3. Click CANCEL to abort the login flow.\n\n")
                            
                            is_logged_in = messagebox.askokcancel(
                                "Google Sign-In", 
                                "1. Log in to your Google/YouTube account in the browser window.\n\n2. Once signed in, click OK here to capture cookies.\n\nClick Cancel to abort."
                            )
                        else:
                            # Go directly to YouTube since the profile might already be logged in
                            await page.goto("https://www.youtube.com")
                            
                            self.append_log("\n[Action Required]:\n")
                            self.append_log("1. Check if you are already logged in to YouTube in the browser window.\n")
                            self.append_log("2. If you are already signed in, click OK here to save cookies.\n")
                            self.append_log("3. If not, log in first and then click OK.\n")
                            self.append_log("4. Click CANCEL to abort.\n\n")
                            
                            is_logged_in = messagebox.askokcancel(
                                "YouTube Cookies", 
                                "Verify you are logged in to YouTube in the browser window.\n\nClick OK here to capture cookies.\n\nClick Cancel to abort."
                            )
                        
                        if is_logged_in:
                            if selected_profile_dir == ".yt_profile":
                                self.append_log(">>> Redirecting to YouTube to generate session cookies...\n")
                                await page.goto("https://www.youtube.com")
                                await page.wait_for_timeout(3000)  # Wait for cookies to write
                            else:
                                self.append_log(">>> Extracting YouTube cookies...\n")
                                await page.wait_for_timeout(2000)
                            
                            cookies = await context.cookies()
                            yt_cookies = [c for c in cookies if 'youtube.com' in c['domain'] or 'youtube' in c['domain']]
                            
                            if not yt_cookies:
                                self.append_log("  [Warning] No YouTube cookies found.\n")
                                
                            cookies_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube_cookies.txt")
                            with open(cookies_file_path, "w", encoding="utf-8") as f:
                                f.write("# Netscape HTTP Cookie File\n")
                                f.write("# http://curl.haxx.se/rfc/cookie_spec.html\n")
                                f.write("# This is a generated file! Do not edit.\n\n")
                                for cookie in cookies:
                                    domain = cookie['domain']
                                    include_subdomains = "TRUE" if domain.startswith('.') or len(domain.split('.')) > 2 else "FALSE"
                                    path = cookie['path']
                                    secure = "TRUE" if cookie['secure'] else "FALSE"
                                    expiry = str(int(cookie.get('expires', 0))) if 'expires' in cookie else "0"
                                    name = cookie['name']
                                    value = cookie['value']
                                    f.write(f"{domain}\t{include_subdomains}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
                                    
                            self.append_log(f"\n[Success] Saved YouTube login cookies to:\n {cookies_file_path}\n")
                            self.update_cookies_status()
                            messagebox.showinfo("Success", "YouTube login cookies saved successfully!")
                        else:
                            self.append_log("\n[Cancelled] YouTube login flow cancelled by user.\n")
                            
                        await context.close()
                except Exception as e:
                    self.append_log(f"\n[Error] Failed during YouTube login: {e}\n")
                    messagebox.showerror("Error", f"Failed during YouTube login: {e}")
                finally:
                    self.set_status("Ready", False)
                    self.toggle_inputs(True)
                    
            asyncio.run(task())
            
        threading.Thread(target=work, daemon=True).start()

    def set_status(self, text, is_active=True):
        self.status_label.config(text=f"Status: {text}")
        if is_active:
            self.status_label.config(foreground=ACCENT_BLUE)
        else:
            self.status_label.config(foreground=ACCENT_GREEN)
            
    def append_log(self, text):
        self.console.insert(tk.END, text)
        self.console.see(tk.END)
        
    def clear_log(self):
        self.console.delete(1.0, tk.END)
        
    def toggle_inputs(self, enable=True):
        state = "normal" if enable else "disabled"
        bg_color = "#313244" if enable else "#1e1e2e"
        
        self.url_entry.config(state=state, bg=bg_color)
        self.dir_entry.config(state=state, bg=bg_color)
        
        if enable:
            self.crawl_btn.config(state="normal", bg=ACCENT_BLUE)
            self.verify_btn.config(state="normal", bg=ACCENT_BLUE)
            self.retry_btn.config(state="normal", bg=ACCENT_BLUE)
            self.cancel_btn.config(state="disabled", bg=BORDER_COLOR, fg=TEXT_COLOR)
            self.is_running = False
        else:
            self.crawl_btn.config(state="disabled", bg="#313244")
            self.verify_btn.config(state="disabled", bg="#313244")
            self.retry_btn.config(state="disabled", bg="#313244")
            self.cancel_btn.config(state="normal", bg=ACCENT_RED, fg="#11111b")
            self.is_running = True

    def run_subprocess_thread(self, cmd_args, status_msg):
        self.clear_log()
        self.toggle_inputs(False)
        self.set_status(status_msg, True)
        
        def work():
            try:
                # Run the process and merge stderr into stdout
                # Startup info hides the black command console box on Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                self.active_process = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding='utf-8',
                    errors='replace',
                    startupinfo=startupinfo
                )
                
                # Stream logs line by line to console
                for line in iter(self.active_process.stdout.readline, ''):
                    # Strip newlines and push to Tkinter
                    self.append_log(line)
                    
                self.active_process.stdout.close()
                self.active_process.wait()
                
                # Completion updates
                exit_code = self.active_process.returncode
                if exit_code == 0:
                    self.append_log("\n>>> Process completed successfully.\n")
                    self.set_status("Finished", False)
                else:
                    self.append_log(f"\n>>> Process stopped or exited with code {exit_code}.\n")
                    self.set_status("Stopped", False)
                    
            except Exception as e:
                self.append_log(f"\n[Execution Error]: {e}\n")
                self.set_status("Error", False)
            finally:
                self.active_process = None
                self.toggle_inputs(True)
                
        threading.Thread(target=work, daemon=True).start()
        
    def trigger_crawl(self):
        url = self.url_var.get().strip()
        save_dir = self.dir_var.get().strip()
        
        if not url:
            messagebox.showerror("Error", "Please enter a valid study guide URL.")
            return
        if not save_dir:
            messagebox.showerror("Error", "Please select a saving folder.")
            return
            
        cmd = [sys.executable, "-u", "crawler.py", url, save_dir, "--no-fallback"]
        self.run_subprocess_thread(cmd, "Crawling...")
        
    def trigger_verify(self):
        url = self.url_var.get().strip()
        save_dir = self.dir_var.get().strip()
        
        if not url or not save_dir:
            messagebox.showerror("Error", "URL and Save Directory must be set.")
            return
            
        cmd = [sys.executable, "-u", "verify_downloads.py", url, "--output-dir", save_dir]
        self.run_subprocess_thread(cmd, "Verifying PDFs...")
        
    def trigger_retry(self):
        url = self.url_var.get().strip()
        save_dir = self.dir_var.get().strip()
        
        if not url or not save_dir:
            messagebox.showerror("Error", "URL and Save Directory must be set.")
            return
            
        cmd = [sys.executable, "-u", "verify_downloads.py", url, "--output-dir", save_dir, "--retry"]
        self.run_subprocess_thread(cmd, "Smart Retrying...")
        
    def cancel_execution(self):
        if self.active_process:
            if messagebox.askyesno("Cancel", "Are you sure you want to stop the current process?"):
                self.append_log("\n>>> Cancelling process... please wait.\n")
                self.active_process.terminate()
                self.active_process = None

if __name__ == "__main__":
    app = App()
    app.mainloop()
