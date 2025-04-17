import tkinter
import tkinter.filedialog
import tkinter.messagebox
import customtkinter
import os
import fnmatch
from pathlib import Path
import threading
import queue
import time
import json  # For saving/loading settings
import platform  # For OS specific actions
import subprocess  # For opening files/folders
import sys  # For finding executable path
import traceback  # For detailed error logging

# Attempt to import gitignore_parser, provide message if missing
try:
    import gitignore_parser
    GITIGNORE_AVAILABLE = True
except ImportError:
    GITIGNORE_AVAILABLE = False
    # Non-blocking warning for GUI
    # print("Warning: 'python-gitignore' package not found. .gitignore parsing will be disabled.")
    # print("Install it using: pip install python-gitignore")


# --- Constants and Default Configuration ---
APP_VERSION = "2.0"
CONFIG_FILENAME = "code_combiner_settings.json"
DEFAULT_CHAR_THRESHOLD = 500000  # Warn if estimated output exceeds 500k chars

DEFAULT_INCLUDE_EXTENSIONS = [
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".php", ".rb", ".swift", ".kt", ".rs", ".scala", ".pl", ".pm",
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
    ".html", ".htm", ".css", ".scss", ".less",
    ".json", ".yaml", ".yml", ".xml", ".toml",
    ".md", ".rst", ".txt", ".sql", ".graphql", ".dockerfile", "Dockerfile",
    ".gitignore", ".gitattributes", ".editorconfig", ".env.example", "LICENSE"
]
DEFAULT_EXCLUDE_PATTERNS = [
    ".git/", ".svn/", ".hg/", "venv/", ".venv/", "env/", "ENV/", "__pycache__/",
    "*.pyc", "*.pyo", "*.pyd", "build/", "dist/", "sdist/", "wheelhouse/",
    "*.egg-info/", ".eggs/", "node_modules/", "package-lock.json", "yarn.lock",
    ".vscode/", ".idea/", "*.sublime-project", "*.sublime-workspace", ".DS_Store",
    "Thumbs.db", "bin/", "obj/", "target/", "out/", "*.png", "*.jpg", "*.jpeg",
    "*.gif", "*.bmp", "*.svg", "*.ico", "*.mp3", "*.wav", "*.ogg", "*.mp4",
    "*.mov", "*.avi", "*.wmv", "*.pdf", "*.doc", "*.docx", "*.xls", "*.xlsx",
    "*.ppt", "*.pptx", "*.zip", "*.tar", "*.gz", "*.bz2", "*.7z", "*.rar",
    "*.db", "*.sqlite", "*.sqlite3", "*.log", "*.lock", "data/", "logs/",
    "coverage/", ".pytest_cache/", ".mypy_cache/", ".tox/"
]

# --- Core Logic Functions (Slightly modified for clarity/robustness) ---


def is_excluded(path: Path, exclude_matcher, root_dir: Path) -> bool:
    """Check if a file/directory path matches gitignore patterns or fnmatch."""
    try:
        abs_path = path.resolve()
        if exclude_matcher and hasattr(exclude_matcher, 'match'):
            return exclude_matcher.match(abs_path)
        # Fallback if no gitignore matcher (using fnmatch on defaults/manual list)
        # Check if it's the pattern list
        elif exclude_matcher and isinstance(exclude_matcher, list):
            exclude_patterns = exclude_matcher
            # Use normalized paths (forward slashes) for pattern matching consistency
            relative_path_str = str(abs_path.relative_to(
                root_dir)).replace(os.sep, '/')
            path_str_normalized = str(abs_path).replace(os.sep, '/')

            for pattern in exclude_patterns:
                normalized_pattern = pattern.replace(os.sep, '/')
                if normalized_pattern.endswith('/'):
                    pattern_dir = normalized_pattern.rstrip('/')
                    # Check relative path match more robustly
                    if relative_path_str == pattern_dir or relative_path_str.startswith(pattern_dir + '/'):
                        return True
                    # Check wildcard dir match
                    if fnmatch.fnmatch(relative_path_str + '/', normalized_pattern):
                        return True
                # Check filename patterns
                elif fnmatch.fnmatch(path.name, normalized_pattern):
                    return True
                # Check full relative path patterns
                elif fnmatch.fnmatch(relative_path_str, normalized_pattern):
                    return True
        return False  # Default to not excluded if no matcher or pattern list provided
    except ValueError:  # Handle relative_to error if path isn't under root
        return False
    except Exception as e:
        # Log error
        print(f"Warning: Error during exclusion check for {path}: {e}")
        return False  # Fail safe: treat as not excluded


def get_language_hint(file_path: Path) -> str:
    # (Function unchanged from previous version)
    extension = file_path.suffix.lower()
    name = file_path.name
    if name == "Dockerfile" or name.lower() == ".dockerfile":
        return "dockerfile"
    if name == ".gitignore":
        return "gitignore"
    if name == ".gitattributes":
        return "gitattributes"
    if name == ".editorconfig":
        return "editorconfig"
    if name == "LICENSE":
        return "text"
    mapping = {".py": "python", ".js": "javascript", ".jsx": "jsx", ".ts": "typescript", ".tsx": "tsx", ".java": "java", ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp", ".cs": "csharp", ".go": "go", ".php": "php", ".rb": "ruby", ".swift": "swift", ".kt": "kotlin", ".rs": "rust", ".scala": "scala", ".pl": "perl", ".sh": "bash",
               ".bash": "bash", ".zsh": "zsh", ".ps1": "powershell", ".bat": "batch", ".cmd": "batch", ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss", ".less": "less", ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".xml": "xml", ".toml": "toml", ".md": "markdown", ".rst": "rst", ".txt": "text", ".sql": "sql", ".graphql": "graphql"}
    return mapping.get(extension, "")


def get_config_path():
    # (Function unchanged)
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).parent
    return app_dir / CONFIG_FILENAME


def combine_codebase_worker(root_dir_str: str, output_file_str: str, include_exts: list[str],
                            exclude_patterns: list[str], use_gitignore: bool,
                            status_queue: queue.Queue, cancel_event: threading.Event):
    """Worker function: scans, counts chars, combines, reports status/progress/errors."""
    files_to_process = []
    exclude_matcher = None
    total_chars = 0
    processed_file_count = 0

    try:
        root_path = Path(root_dir_str).resolve()
        output_path = Path(output_file_str)

        status_queue.put(('status', f"Preparing exclude patterns..."))
        # --- Prepare Exclusions ---
        final_exclude_patterns = list(
            set(DEFAULT_EXCLUDE_PATTERNS + exclude_patterns))
        gitignore_path = root_path / ".gitignore"
        # Create the matcher based on settings
        if use_gitignore and GITIGNORE_AVAILABLE and gitignore_path.is_file():
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as gf:
                    exclude_matcher = gitignore_parser.parse(gf)
                status_queue.put(
                    ('status', f"Using exclusions from: {gitignore_path}"))
            except Exception as e:
                status_queue.put(('error', "gitignore Parse Error",
                                 f"Could not read or parse .gitignore: {e}\nUsing manual excludes only."))
                # Pass pattern list for fnmatch fallback
                exclude_matcher = final_exclude_patterns
        else:
            # Pass pattern list for fnmatch fallback
            exclude_matcher = final_exclude_patterns
            if use_gitignore and not gitignore_path.is_file():
                status_queue.put(
                    ('status', "Info: '.gitignore' file not found in root directory. Using manual excludes."))
            elif use_gitignore and not GITIGNORE_AVAILABLE:
                status_queue.put(
                    ('status', "Warning: python-gitignore not installed. Using manual excludes."))

        # --- Step 1: Scan & Collect Files ---
        status_queue.put(('status', f"Scanning directory: {root_path}"))
        # Start indeterminate progress
        status_queue.put(('progress_mode', 'indeterminate', None))
        start_time = time.time()

        paths_to_scan = [root_path]
        # Add root initially to avoid reprocessing if it's passed again
        processed_dirs = {root_path}

        while paths_to_scan:
            if cancel_event.is_set():
                status_queue.put(
                    ('done', False, "Cancelled by user during scan."))
                return

            current_path = paths_to_scan.pop(0)
            if not current_path.exists():
                continue

            # Check exclusion (works for both files and dirs)
            if current_path != root_path and is_excluded(current_path, exclude_matcher, root_path):
                continue

            if current_path.is_dir():
                try:
                    items = list(current_path.iterdir())  # Get items first
                    for item in items:
                        if item.is_dir() and item not in processed_dirs:
                            processed_dirs.add(item)
                            paths_to_scan.append(item)
                        elif item.is_file():
                            # Check file exclusion immediately
                            if not is_excluded(item, exclude_matcher, root_path):
                                # Check include extensions
                                if item.suffix.lower() in include_exts or item.name in include_exts:
                                    files_to_process.append(item)

                except PermissionError:
                    status_queue.put(
                        ('status', f"Warning: Permission denied scanning: {current_path.relative_to(root_path)}"))
                except OSError as e:
                    status_queue.put(
                        ('status', f"Warning: Error scanning {current_path.relative_to(root_path)}: {e}"))
            # Files encountered directly at root (or passed via non-dir scan?) handled by iterdir above
            # This block might be redundant if starting with root_path only
            # elif current_path.is_file():
            #      if not is_excluded(current_path, exclude_matcher, root_path):
            #          if current_path.suffix.lower() in include_exts or current_path.name in include_exts:
            #              if current_path not in files_to_process: # Avoid duplicates
            #                  files_to_process.append(current_path)

        scan_duration = time.time() - start_time
        status_queue.put(
            ('status', f"Scan complete. Found {len(files_to_process)} files in {scan_duration:.2f} seconds."))

        if not files_to_process:
            status_queue.put(
                ('status', "No files found to include. Output file will not be created."))
            # Stop progress
            status_queue.put(('progress_mode', 'determinate', (0, 1)))
            status_queue.put(('done', False, "No files included."))
            return

        # --- Step 2: Estimate Size (Character Count) ---
        status_queue.put(('status', f"Estimating total size..."))
        for i, file_path in enumerate(sorted(files_to_process)):
            if cancel_event.is_set():
                status_queue.put(
                    ('done', False, "Cancelled by user during size estimation."))
                return
            status_queue.put(
                ('current_file', f"Estimating: {file_path.relative_to(root_path)}"))
            # Update progress during estimation
            status_queue.put(('progress', i + 1, len(files_to_process)))
            try:
                total_chars += len(file_path.read_text(encoding="utf-8"))
            except Exception:
                pass  # Ignore errors during estimation, handle properly during writing
        status_queue.put(('total_chars', total_chars))  # Send total char count

        # --- Step 3: Write Output ---
        status_queue.put(
            ('status', f"Writing {len(files_to_process)} files ({total_chars:,} chars) to: {output_path.name}"))
        # Reset progress for writing phase
        status_queue.put(('progress_mode', 'determinate',
                         (0, len(files_to_process))))
        status_queue.put(('current_file', 'Starting write...'))
        start_time = time.time()
        written_count = 0
        total_files_to_write = len(files_to_process)

        with open(output_path, "w", encoding="utf-8") as outfile:
            for i, file_path in enumerate(sorted(files_to_process)):
                if cancel_event.is_set():
                    status_queue.put(
                        ('done', False, "Cancelled by user during write."))
                    return

                relative_path_str = str(file_path.relative_to(
                    root_path)).replace(os.sep, '/')
                status_queue.put(('current_file', relative_path_str))
                status_queue.put(('progress', i + 1, total_files_to_write))

                outfile.write(f"# File: {relative_path_str}\n\n")
                lang_hint = get_language_hint(file_path)
                outfile.write(f"```{lang_hint}\n")
                try:
                    content = file_path.read_text(encoding="utf-8")
                    outfile.write(content.strip() + "\n")
                    written_count += 1
                except UnicodeDecodeError:
                    outfile.write(
                        "--- Error: Could not decode file content (likely binary) ---\n")
                    status_queue.put(
                        ('status', f"Warning: Skipped binary file: {relative_path_str}"))
                except PermissionError:
                    outfile.write(
                        f"--- Error reading file: Permission Denied ---\n")
                    status_queue.put(
                        ('error', 'File Read Error', f"Permission denied reading: {relative_path_str}"))
                except Exception as e:
                    outfile.write(f"--- Error reading file: {e} ---\n")
                    status_queue.put(
                        ('error', 'File Read Error', f"Error reading {relative_path_str}: {e}"))
                outfile.write("```\n\n")

        write_duration = time.time() - start_time
        final_message = f"Successfully combined {written_count}/{total_files_to_write} files ({total_chars:,} chars) into '{output_path.name}' in {write_duration:.2f} seconds."
        status_queue.put(('status', final_message))
        status_queue.put(
            ('progress', total_files_to_write, total_files_to_write))
        status_queue.put(('done', True, final_message))

    except Exception as e:
        detailed_error = traceback.format_exc()
        status_queue.put(
            ('status', f"Error: An unexpected critical error occurred: {e}"))
        status_queue.put(('status', f"Details: {detailed_error}"))
        status_queue.put(('error', 'Critical Error',
                         f"An unexpected error occurred: {e}\n\nDetails logged."))
        # Reset progress
        status_queue.put(('progress_mode', 'determinate', (0, 1)))
        status_queue.put(('done', False, f"Failed with critical error: {e}"))


# --- GUI Application Class ---

class CodeCombinerApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # --- Load Initial Settings ---
        # Load theme/mode first before creating widgets
        self.settings = self._load_settings(
            initial=True)  # Load or get defaults
        customtkinter.set_appearance_mode(
            self.settings.get("appearance_mode", "System"))
        customtkinter.set_default_color_theme(
            self.settings.get("color_theme", "blue"))

        self.title(f"Codebase Combiner for LLM v{APP_VERSION}")
        self.geometry("900x800")  # Increased size
        self.minsize(750, 650)

        # --- State Variables ---
        self.input_dir_path = tkinter.StringVar(
            value=self.settings.get("last_input_dir", ""))
        self.output_file_path = tkinter.StringVar()
        # Load last output dir, but not filename
        last_output_dir = self.settings.get("last_output_dir", "")
        self.last_output_dir = last_output_dir if last_output_dir else str(
            Path.home())

        self.status_queue = queue.Queue()
        self.processing_thread = None
        self.cancel_event = threading.Event()
        self.current_file_var = tkinter.StringVar(value="N/A")
        self.char_count_var = tkinter.StringVar(value="Est. Chars: N/A")
        self.char_threshold_var = tkinter.StringVar(
            value=str(self.settings.get("char_threshold", DEFAULT_CHAR_THRESHOLD)))

        self._create_menu()
        self._create_widgets()
        self._apply_loaded_settings()  # Populate widgets with loaded settings
        self.check_paths_set()  # Initial check for button state
        self.process_status_queue()  # Start queue polling

    def _create_menu(self):
        self.menu_bar = tkinter.Menu(self)
        # On macOS, the menu doesn't automatically appear without this setup
        if platform.system() == "Darwin":
            app_menu = tkinter.Menu(self.menu_bar, name='apple')
            self.menu_bar.add_cascade(menu=app_menu)
            # Add standard macOS items if desired (e.g., app_menu.add_command(label='About...'))
            # If adding standard items, you might remove the "Help -> About" below for macOS

        # --- Options Menu ---
        self.options_menu = tkinter.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Options", menu=self.options_menu)

        # Appearance Mode Submenu
        self.appearance_mode_menu = tkinter.Menu(self.options_menu, tearoff=0)
        self.options_menu.add_cascade(
            label="Appearance Mode", menu=self.appearance_mode_menu)
        self.appearance_mode_var = tkinter.StringVar(
            value=customtkinter.get_appearance_mode())
        # --- CORRECTION: Use label= ---
        self.appearance_mode_menu.add_radiobutton(
            label="Light", variable=self.appearance_mode_var, value="Light", command=lambda: self.change_appearance_mode("Light"))
        self.appearance_mode_menu.add_radiobutton(
            label="Dark", variable=self.appearance_mode_var, value="Dark", command=lambda: self.change_appearance_mode("Dark"))
        self.appearance_mode_menu.add_radiobutton(
            label="System", variable=self.appearance_mode_var, value="System", command=lambda: self.change_appearance_mode("System"))

        # Color Theme Submenu
        self.color_theme_menu = tkinter.Menu(self.options_menu, tearoff=0)
        self.options_menu.add_cascade(
            label="Color Theme", menu=self.color_theme_menu)
        self.color_theme_var = tkinter.StringVar(
            value=self.settings.get("color_theme", "blue"))
        # --- CORRECTION: Use label= ---
        self.color_theme_menu.add_radiobutton(
            label="Blue", variable=self.color_theme_var, value="blue", command=lambda: self.change_color_theme("blue"))
        self.color_theme_menu.add_radiobutton(
            label="Green", variable=self.color_theme_var, value="green", command=lambda: self.change_color_theme("green"))
        self.color_theme_menu.add_radiobutton(label="Dark Blue", variable=self.color_theme_var,
                                              value="dark-blue", command=lambda: self.change_color_theme("dark-blue"))

        self.options_menu.add_separator()
        self.options_menu.add_command(
            label="Save All Settings Now", command=self._save_settings)

        # --- Help Menu ---
        self.help_menu = tkinter.Menu(self.menu_bar, tearoff=0)
        # Add Help menu *after* Options for standard placement
        self.menu_bar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(
            label="About", command=self.show_about_dialog)

        # Set the menu to the window *after* creating it (especially for Windows/Linux)
        self.config(menu=self.menu_bar)
    def change_appearance_mode(self, mode: str):
        customtkinter.set_appearance_mode(mode)
        # Update internal settings cache
        self.settings["appearance_mode"] = mode

    def change_color_theme(self, theme: str):
        # Changing theme might require recreating widgets or might have limited effect after init
        # For now, just save the preference for next launch
        self.settings["color_theme"] = theme
        tkinter.messagebox.showinfo(
            "Theme Change", f"Theme set to '{theme}'. Restart the application to see the full effect.")
        # Or attempt a more complex dynamic update if needed

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)  # Allow tab view to expand

        # --- Tab View ---
        self.tab_view = customtkinter.CTkTabview(self)
        self.tab_view.grid(row=0, column=0, padx=10, pady=(
            0, 10), sticky="nsew")  # Reduced top pady
        self.tab_view.add("Run")
        self.tab_view.add("Settings")
        self.tab_view.set("Run")  # Start on Run tab

        # --- "Run" Tab ---
        run_tab = self.tab_view.tab("Run")
        run_tab.grid_columnconfigure(0, weight=1)
        run_tab.grid_rowconfigure(2, weight=1)  # Status box expansion

        # Input/Output Frame
        io_frame = customtkinter.CTkFrame(run_tab)
        io_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        io_frame.grid_columnconfigure(1, weight=1)

        input_dir_label = customtkinter.CTkLabel(
            io_frame, text="Codebase Root Directory:")
        input_dir_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.input_dir_entry = customtkinter.CTkEntry(
            io_frame, textvariable=self.input_dir_path, state="readonly")
        self.input_dir_entry.grid(
            row=0, column=1, padx=(0, 5), pady=5, sticky="ew")
        input_dir_button = customtkinter.CTkButton(
            io_frame, text="Browse...", width=80, command=self.browse_directory)
        input_dir_button.grid(row=0, column=2, padx=(0, 10), pady=5)

        output_file_label = customtkinter.CTkLabel(
            io_frame, text="Output Markdown File:")
        output_file_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.output_file_entry = customtkinter.CTkEntry(
            io_frame, textvariable=self.output_file_path, state="readonly")
        self.output_file_entry.grid(
            row=1, column=1, padx=(0, 5), pady=5, sticky="ew")
        output_file_button = customtkinter.CTkButton(
            io_frame, text="Save As...", width=80, command=self.select_output_file)
        output_file_button.grid(row=1, column=2, padx=(0, 10), pady=5)

        # Open Buttons Frame
        open_btn_frame = customtkinter.CTkFrame(
            io_frame, fg_color="transparent")
        open_btn_frame.grid(row=1, column=3, padx=(5, 10), pady=5, sticky="e")
        self.open_folder_button = customtkinter.CTkButton(
            open_btn_frame, text="Open Folder", width=100, command=self.open_output_folder, state="disabled")
        self.open_folder_button.pack(side="left", padx=(0, 5))
        self.open_file_button = customtkinter.CTkButton(
            open_btn_frame, text="Open File", width=100, command=self.open_output_file, state="disabled")
        self.open_file_button.pack(side="left")

        # Action/Status Frame
        action_frame = customtkinter.CTkFrame(run_tab)
        action_frame.grid(row=1, column=0, rowspan=2,
                          padx=10, pady=5, sticky="nsew")
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_rowconfigure(3, weight=1)  # Status box expansion

        # Combine/Cancel Buttons
        btn_sub_frame = customtkinter.CTkFrame(
            action_frame, fg_color="transparent")
        btn_sub_frame.grid(row=0, column=0, columnspan=2, pady=10, sticky="ew")
        # Center buttons within this sub-frame using column weights
        btn_sub_frame.grid_columnconfigure(0, weight=1)
        btn_sub_frame.grid_columnconfigure(1, weight=0)  # Button 1
        btn_sub_frame.grid_columnconfigure(2, weight=0)  # Button 2
        btn_sub_frame.grid_columnconfigure(3, weight=1)

        self.combine_button = customtkinter.CTkButton(
            btn_sub_frame, text="Combine Codebase", command=self.start_combination_thread)
        self.combine_button.grid(row=0, column=1, padx=(10, 5))
        self.combine_button.configure(state="disabled")

        self.cancel_button = customtkinter.CTkButton(
            btn_sub_frame, text="Cancel", command=self.cancel_combination, state="disabled", fg_color="#D32F2F", hover_color="#B71C1C")  # Red colors
        self.cancel_button.grid(row=0, column=2, padx=(5, 10))

        # Progress Bar & Current File
        progress_frame = customtkinter.CTkFrame(
            action_frame, fg_color="transparent")
        progress_frame.grid(row=1, column=0, columnspan=2,
                            padx=10, pady=5, sticky="ew")
        progress_frame.grid_columnconfigure(
            1, weight=1)  # Make progress bar expand

        progress_label = customtkinter.CTkLabel(
            progress_frame, text="Progress:")
        progress_label.grid(row=0, column=0, padx=(0, 5), sticky="w")
        self.progress_bar = customtkinter.CTkProgressBar(progress_frame)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=1, padx=5, sticky="ew")
        # Track mode ('determinate' or 'indeterminate')
        self.progress_bar_mode = 'determinate'

        current_file_label = customtkinter.CTkLabel(
            progress_frame, text="Current Task:")
        current_file_label.grid(row=1, column=0, padx=(
            0, 5), pady=(5, 0), sticky="w")
        self.current_file_display = customtkinter.CTkLabel(
            # Adjust wraplength
            progress_frame, textvariable=self.current_file_var, anchor="w", wraplength=650)
        self.current_file_display.grid(
            row=1, column=1, columnspan=2, pady=(5, 0), padx=5, sticky="ew")

        # Estimated Size Label
        self.char_count_label = customtkinter.CTkLabel(
            progress_frame, textvariable=self.char_count_var, anchor="w")
        self.char_count_label.grid(row=0, column=2, padx=(10, 0), sticky='e')

        # Status Log
        status_label = customtkinter.CTkLabel(action_frame, text="Status Log:")
        status_label.grid(row=2, column=0, columnspan=2,
                          padx=10, pady=(10, 0), sticky="w")
        self.status_textbox = customtkinter.CTkTextbox(
            action_frame, state="disabled", height=150)
        self.status_textbox.grid(
            row=3, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")

        # --- "Settings" Tab ---
        settings_tab = self.tab_view.tab("Settings")
        settings_tab.grid_columnconfigure(0, weight=1)
        settings_tab.grid_rowconfigure(
            3, weight=1)  # Exclude textbox expansion

        # Include Frame
        include_frame = customtkinter.CTkFrame(settings_tab)
        include_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        include_frame.grid_columnconfigure(0, weight=1)

        include_label = customtkinter.CTkLabel(
            include_frame, text="Include Extensions/Filenames (comma-separated):")
        include_label.pack(padx=10, pady=(5, 0), anchor="w")
        self.include_entry = customtkinter.CTkEntry(include_frame)
        self.include_entry.pack(padx=10, pady=(0, 10), fill="x", expand=True)

        # Exclude Frame
        exclude_frame = customtkinter.CTkFrame(settings_tab)
        exclude_frame.grid(row=1, column=0, rowspan=3,
                           padx=10, pady=5, sticky="nsew")
        exclude_frame.grid_columnconfigure(0, weight=1)
        exclude_frame.grid_rowconfigure(1, weight=1)

        exclude_label = customtkinter.CTkLabel(
            exclude_frame, text="Exclude Patterns (one per line, .gitignore syntax if enabled below):")
        exclude_label.grid(row=0, column=0, padx=10, pady=(5, 0), sticky="nw")
        self.exclude_textbox = customtkinter.CTkTextbox(
            exclude_frame, height=200)
        self.exclude_textbox.grid(
            row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # Gitignore Checkbox & Char Threshold
        options_frame = customtkinter.CTkFrame(
            exclude_frame, fg_color="transparent")
        options_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        options_frame.grid_columnconfigure(
            1, weight=1)  # Push threshold to the right

        self.use_gitignore_var = tkinter.BooleanVar()
        # --- Problematic Line Below ---
        self.gitignore_checkbox = customtkinter.CTkCheckBox(
            options_frame, text="Use .gitignore (if found)", # Keep text concise here
            variable=self.use_gitignore_var
        )
        # --- End Problematic Block ---

        self.gitignore_checkbox.grid(row=0, column=0, padx=(0, 20), sticky="w")
        if not GITIGNORE_AVAILABLE:
            # Update text here if tooltip is removed, to give user context
            self.gitignore_checkbox.configure(
                state="disabled", text="Use .gitignore (requires python-gitignore)")
        threshold_label = customtkinter.CTkLabel(
            options_frame, text="Warn if Chars >")
        threshold_label.grid(row=0, column=2, padx=(0, 5), sticky="e")
        self.threshold_entry = customtkinter.CTkEntry(
            options_frame, textvariable=self.char_threshold_var, width=100)
        self.threshold_entry.grid(row=0, column=3, sticky="e")

        # Save/Load Buttons Frame (Now at the bottom of the settings tab)
        config_btn_frame = customtkinter.CTkFrame(settings_tab)
        config_btn_frame.grid(row=4, column=0, padx=10,
                              pady=(5, 10), sticky="ew")
        config_btn_frame.grid_columnconfigure(0, weight=1)  # Center buttons
        config_btn_frame.grid_columnconfigure(1, weight=1)

        save_settings_button = customtkinter.CTkButton(
            config_btn_frame, text="Save Settings Now", command=self._save_settings)
        save_settings_button.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        load_settings_button = customtkinter.CTkButton(
            config_btn_frame, text="Reload Saved Settings", command=self._load_settings)
        load_settings_button.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # --- Set Window Icon ---
        self.set_app_icon()

    # --- Methods for File Handling, Settings, Threading, Status ---

    def set_app_icon(self):
        # (Method unchanged from previous detailed plan)
        icon_path = None
        if getattr(sys, 'frozen', False):
            app_dir = Path(sys.executable).parent
        else:
            app_dir = Path(__file__).parent
        potential_icon = app_dir / "checker_icon.ico"  # Assumed name
        if potential_icon.exists() and platform.system() == "Windows":
            icon_path = str(potential_icon)
            try:
                self.iconbitmap(default=icon_path)
            except Exception as e:
                print(f"Warning: Failed to set .ico: {e}")
        else:
            potential_icon_img = app_dir / "checker_icon.png"  # Fallback
            if potential_icon_img.exists():
                try:
                    icon_image = tkinter.PhotoImage(
                        file=str(potential_icon_img))
                    self.iconphoto(True, icon_image)
                except Exception as e:
                    print(f"Warning: Failed to set .png: {e}")
            # else: print("Warning: No suitable icon file found.")

    def _load_settings(self, initial=False):
        """Loads settings from the JSON config file or returns defaults."""
        config_file = get_config_path()
        default_settings = {
            "include_extensions": DEFAULT_INCLUDE_EXTENSIONS,
            "exclude_patterns": DEFAULT_EXCLUDE_PATTERNS,
            "use_gitignore": False,
            "appearance_mode": "System",
            "color_theme": "blue",
            "last_input_dir": str(Path.home()),
            "last_output_dir": str(Path.home()),
            "char_threshold": DEFAULT_CHAR_THRESHOLD
        }
        try:
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    loaded_settings = json.load(f)
                    # Merge loaded settings with defaults (defaults provide missing keys)
                    default_settings.update(loaded_settings)
                if not initial:
                    self.update_status(
                        f"Settings loaded from {config_file.name}")
            else:
                if not initial:
                    self.update_status(
                        "No settings file found, using defaults.")
        except Exception as e:
            if not initial:
                self.update_status(
                    f"Error loading settings: {e}. Using defaults.")
                messagebox.showerror(
                    "Settings Error", f"Could not load settings from {config_file.name}:\n{e}")
        return default_settings  # Return merged/default settings

    def _apply_loaded_settings(self):
        """Applies the loaded self.settings to the GUI widgets."""
        self.include_entry.delete(0, "end")
        self.include_entry.insert(0, ", ".join(self.settings.get(
            "include_extensions", DEFAULT_INCLUDE_EXTENSIONS)))

        self.exclude_textbox.delete("1.0", "end")
        self.exclude_textbox.insert("1.0", "\n".join(
            self.settings.get("exclude_patterns", DEFAULT_EXCLUDE_PATTERNS)))

        self.use_gitignore_var.set(self.settings.get("use_gitignore", False))
        self.char_threshold_var.set(
            str(self.settings.get("char_threshold", DEFAULT_CHAR_THRESHOLD)))
        # Input/Output paths already set in __init__ from loaded settings

    def _save_settings(self):
        """Saves current settings to the JSON config file."""
        config_file = get_config_path()
        try:
            include_str = self.include_entry.get()
            self.settings["include_extensions"] = [ext for ext in (
                e.strip() for e in include_str.split(',')) if ext]

            exclude_str = self.exclude_textbox.get("1.0", "end-1c")
            self.settings["exclude_patterns"] = [patt for patt in (
                p.strip() for p in exclude_str.splitlines()) if patt]

            self.settings["use_gitignore"] = self.use_gitignore_var.get()
            self.settings["appearance_mode"] = self.appearance_mode_var.get()
            # Save selected theme
            self.settings["color_theme"] = self.color_theme_var.get()
            self.settings["last_input_dir"] = self.input_dir_path.get() or str(
                Path.home())
            self.settings["last_output_dir"] = str(Path(self.output_file_path.get(
            )).parent) if self.output_file_path.get() else self.last_output_dir

            try:
                self.settings["char_threshold"] = int(
                    self.threshold_entry.get())
            except ValueError:
                messagebox.showerror(
                    "Settings Error", "Invalid character threshold. Please enter a number.")
                return  # Don't save if threshold is invalid

            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
            self.update_status(f"Settings saved to {config_file.name}")
        except Exception as e:
            self.update_status(f"Error saving settings: {e}")
            messagebox.showerror(
                "Settings Error", f"Could not save settings to {config_file.name}:\n{e}")

    def browse_directory(self):
        last_dir = self.input_dir_path.get() or self.settings.get(
            "last_input_dir", str(Path.home()))
        dir_path = tkinter.filedialog.askdirectory(
            title="Select Codebase Root Directory",
            initialdir=last_dir if Path(
                last_dir).is_dir() else str(Path.home())
        )
        if dir_path:
            self.input_dir_path.set(dir_path)
            # Update setting immediately for next time
            self.settings["last_input_dir"] = dir_path
            self.check_paths_set()

    def select_output_file(self):
        last_dir = self.last_output_dir  # Get stored dir
        file_path = tkinter.filedialog.asksaveasfilename(
            title="Select Output Markdown File",
            initialdir=last_dir if Path(
                last_dir).is_dir() else str(Path.home()),
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"),
                       ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            self.output_file_path.set(file_path)
            self.last_output_dir = str(
                Path(file_path).parent)  # Update last dir used
            # Update internal cache
            self.settings["last_output_dir"] = self.last_output_dir
            self.check_paths_set()

    def check_paths_set(self):
        # (Method mostly unchanged - enables/disables Combine, Open File, Open Folder)
        in_path = self.input_dir_path.get()
        out_path = self.output_file_path.get()
        can_combine = bool(in_path and out_path)
        self.combine_button.configure(
            state="normal" if can_combine else "disabled")

        output_exists = bool(out_path and Path(out_path).exists())
        output_dir_valid = bool(out_path and Path(out_path).parent.is_dir())

        self.open_file_button.configure(
            state="normal" if output_exists else "disabled")
        self.open_folder_button.configure(
            state="normal" if output_dir_valid else "disabled")

    def update_status(self, message):
        # (Method unchanged - adds timestamp)
        self.status_textbox.configure(state="normal")
        self.status_textbox.insert(
            "end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.status_textbox.see("end")  # Auto-scroll
        self.status_textbox.configure(state="disabled")

    def update_progress(self, current, total):
        # (Method unchanged)
        if total > 0:
            progress = float(current) / float(total)
            self.progress_bar.set(progress)
        else:
            self.progress_bar.set(0)

    def update_current_file(self, filename):
        # (Method unchanged)
        self.current_file_var.set(filename if filename else "N/A")

    def process_status_queue(self):
        """Checks the queue for messages and updates the GUI."""
        try:
            while True:  # Process all messages currently in queue
                message_type, *payload = self.status_queue.get_nowait()

                if message_type == "status":
                    self.update_status(payload[0])
                elif message_type == "progress":
                    # Only update if in determinate mode
                    if self.progress_bar_mode == 'determinate':
                        self.update_progress(payload[0], payload[1])
                elif message_type == "progress_mode":
                    mode, data = payload
                    self.progress_bar_mode = mode
                    if mode == 'indeterminate':
                        self.progress_bar.configure(mode='indeterminate')
                        self.progress_bar.start()
                    else:  # determinate
                        self.progress_bar.stop()
                        self.progress_bar.configure(mode='determinate')
                        if data:
                            self.update_progress(data[0], data[1])
                elif message_type == "current_file":
                    self.update_current_file(payload[0])
                elif message_type == "total_chars":
                    total_chars = payload[0]
                    self.char_count_var.set(f"Est. Chars: {total_chars:,}")
                    try:
                        threshold = int(self.threshold_entry.get())
                        if total_chars > threshold:
                            warning_msg = f"Estimated character count ({total_chars:,}) exceeds warning threshold ({threshold:,})."
                            self.update_status(f"Warning: {warning_msg}")
                            messagebox.showwarning(
                                "Size Warning", warning_msg)
                    except ValueError:
                        self.update_status(
                            "Warning: Invalid character threshold setting.")

                elif message_type == "error":
                    # Show major errors in a popup, keep details in log
                    title, message = payload
                    self.update_status(
                        f"ERROR: {title} - {message}")  # Log it too
                    messagebox.showerror(title, message)

                elif message_type == "done":
                    success, final_message = payload
                    # Stop indeterminate progress bar if it was running
                    if self.progress_bar_mode == 'indeterminate':
                        self.progress_bar.stop()
                        self.progress_bar.configure(mode='determinate')

                    self.combine_button.configure(
                        state="normal")  # Re-enable combine
                    self.cancel_button.configure(state="disabled")
                    self.update_current_file("N/A")  # Clear current file
                    if success:
                        self.progress_bar.set(1.0)  # Ensure 100%
                        self.check_paths_set()  # Update open buttons state
                        messagebox.showinfo("Success", final_message)
                    else:
                        self.progress_bar.set(0)  # Reset on failure/cancel
                        if "Cancelled" not in final_message:  # Don't show error box if cancelled
                            messagebox.showerror("Failed", final_message)

                    self.processing_thread = None  # Clear thread reference
                    return  # Exit queue processing loop for this cycle

        except queue.Empty:
            pass  # No messages currently

        # Schedule the next check ONLY if a thread is known to be running
        if self.processing_thread and self.processing_thread.is_alive():
            self.after(100, self.process_status_queue)

    def start_combination_thread(self):
        # (Method mostly unchanged, validates paths, gets settings, starts thread)
        in_dir = self.input_dir_path.get()
        out_file = self.output_file_path.get()
        if not in_dir or not out_file:
            messagebox.showerror(
                "Input Error", "Please select both input directory and output file.")
            return
        if not Path(in_dir).is_dir():
            messagebox.showerror(
                "Input Error", f"Input directory not found:\n{in_dir}")
            return

        # Clear previous status/progress
        self.status_textbox.configure(state="normal")
        self.status_textbox.delete("1.0", "end")
        self.status_textbox.configure(state="disabled")
        self.progress_bar.set(0)
        self.progress_bar.stop()
        self.progress_bar.configure(mode='determinate')
        self.update_current_file("Preparing...")
        self.char_count_var.set("Est. Chars: N/A")
        self.update_status("Starting process...")

        # Get include/exclude settings
        include_str = self.include_entry.get()
        include_extensions = [ext for ext in (
            e.strip() for e in include_str.split(',')) if ext]
        include_extensions = [ext if ext.startswith(
            '.') or '.' not in ext else '.' + ext for ext in include_extensions]

        exclude_str = self.exclude_textbox.get("1.0", "end-1c")
        exclude_patterns = [patt for patt in (
            p.strip() for p in exclude_str.splitlines()) if patt]
        use_gitignore = self.use_gitignore_var.get()

        self.combine_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.cancel_event.clear()

        self.processing_thread = threading.Thread(
            target=combine_codebase_worker,
            args=(in_dir, out_file, include_extensions, exclude_patterns,
                  use_gitignore, self.status_queue, self.cancel_event),
            daemon=True
        )
        self.processing_thread.start()
        self.after(100, self.process_status_queue)

    def cancel_combination(self):
        # (Method unchanged)
        if self.processing_thread and self.processing_thread.is_alive():
            self.update_status("Cancellation requested...")
            self.cancel_event.set()
            self.cancel_button.configure(state="disabled")

    def open_output_file(self):
        # (Method unchanged)
        filepath = self.output_file_path.get()
        if not filepath or not Path(filepath).exists():
            self.update_status(
                "Error: Output file does not exist or path not set.")
            messagebox.showwarning(
                "File Not Found", "The specified output file does not exist.")
            return
        try:
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin":
                subprocess.call(["open", filepath])
            else:
                subprocess.call(["xdg-open", filepath])
        except Exception as e:
            self.update_status(f"Error opening file: {e}")
            messagebox.showerror(
                "Error", f"Could not open the file.\nError: {e}")

    def open_output_folder(self):
        # (Method unchanged)
        filepath = self.output_file_path.get()
        if not filepath:
            self.update_status("Error: Output file path not set.")
            messagebox.showwarning(
                "Path Not Set", "Please select an output file first.")
            return
        folder_path = str(Path(filepath).parent)
        if not Path(folder_path).is_dir():
            self.update_status(
                f"Error: Output folder not found: {folder_path}")
            messagebox.showwarning(
                "Folder Not Found", f"The folder containing the output file could not be found:\n{folder_path}")
            return
        try:
            if platform.system() == "Windows":
                os.startfile(folder_path)
            elif platform.system() == "Darwin":
                subprocess.call(["open", folder_path])
            else:
                subprocess.call(["xdg-open", folder_path])
        except Exception as e:
            self.update_status(f"Error opening folder: {e}")
            messagebox.showerror(
                "Error", f"Could not open the folder.\nError: {e}")

    def show_about_dialog(self):
        # (Method unchanged, remember to customize)
        messagebox.showinfo(
            "About Codebase Combiner",
            f"Codebase Combiner for LLM\n\n"
            f"Version: {APP_VERSION}\n"
            "Created by: [Your Name/Team]\n\n"  # Customize this
            "This tool helps combine source code files from a directory into a single Markdown file, suitable for analysis by Large Language Models."
        )

    def on_closing(self):
        """Called when the window is closed."""
        print("Saving settings on exit...")
        self._save_settings()  # Attempt to save settings on exit
        self.destroy()


# --- Main Execution ---
if __name__ == "__main__":
    app = CodeCombinerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)  # Save settings on close
    app.mainloop()
