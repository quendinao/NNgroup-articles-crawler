import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import subprocess

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
