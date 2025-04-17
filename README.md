# Code Combiner for LLM Utility v1.0

A simple desktop tool to scan a codebase directory, select relevant source files, and combine them into a single, structured Markdown file suitable for analysis by Large Language Models (LLMs).

## Purpose

LLMs often have limits on the amount of text (context window) they can process at once. This tool helps prepare a large codebase for an LLM by:
* Selecting only relevant source code files based on configurable filters.
* Excluding unnecessary files and directories (like virtual environments, build artifacts, `.git` folders).
* Optionally using your project's `.gitignore` file for exclusions.
* Combining the content into one file, clearly marking the original path of each included file.
* Estimating the output size (character count) to help manage context limits.

## Features (v1.0)

* Scans codebase directories recursively.
* Combines selected files into a single Markdown (`.md`) output file.
* Includes file paths as headers and uses fenced code blocks (with language hints) for readability.
* **Configurable Filters:**
    * Specify file extensions/names to **include**.
    * Specify file/directory patterns to **exclude** (uses `.gitignore` syntax if enabled).
    * Option to automatically use the project's `.gitignore` file (requires `python-gitignore` package).
* **User-Friendly GUI:**
    * Easy selection of input directory and output file.
    * Tabbed interface for Run controls and Settings.
    * Displays processing status, progress bar, and currently processed file.
    * **Cancel** button to stop long operations.
    * Buttons to **Open Output File** or **Open Containing Folder**.
* **Configuration:**
    * **Save/Load Settings:** Include/Exclude lists and other preferences are saved to `code_combiner_settings.json` (located next to the application) and loaded on startup.
    * Remembers last used input/output directories.
* **LLM Context Helper:**
    * Estimates total **character count** of the combined output.
    * Configurable threshold to **warn** if the estimated size is large.
* **Customization:**
    * Select **Appearance Mode** (Light/Dark/System) and **Color Theme** (Blue/Green/Dark-Blue) via the Options menu (requires restart for full theme change).
* **Standalone Executable:** Packaged for Windows, no Python installation needed for end-users.

## Getting Started (For End Users)

Follow these steps to download and run the tool:

1.  **Download:**
    * Get the `CodeCombiner.exe` file (or the ZIP containing it and this guide) from:
        * **[Link to Shared Drive/Cloud Storage where you placed the .exe or .zip file]**
        *(Remember to replace this bracketed text with the actual link or location!)*
2.  **Save/Unzip:**
    * Save the `CodeCombiner.exe` file somewhere convenient, like your **Desktop** or a dedicated **Tools** folder.
    * *(If you downloaded a ZIP file, right-click it and select "Extract All..." to unzip the contents first. Run the `.exe` from the unzipped folder.)*
    * **Important:** The application saves its settings (`code_combiner_settings.json`) in the *same folder* as the `.exe`. Ensure you run it from a location where it has permission to write files (e.g., Desktop, Documents, Downloads are usually fine; Program Files might cause issues).
3.  **Run (First Time Only - Important Security Steps):**
    * Find the `CodeCombiner.exe` file you saved and double-click it.
    * **Windows Security Warning:** You will likely see a blue screen saying **"Windows protected your PC"**. This is normal for simple tools like this that aren't from the Microsoft Store. **Do not click "Don't run"**.
        * **(1) Click the `More info` link.**
        * **(2) Click the `Run anyway` button.**
    * **(If using on macOS - Note: This guide focuses on the Windows build):** If you see a message like *"CodeCombiner" can't be opened because it is from an unidentified developer"*: Right-click (or Control-click) the app icon -> `Open` -> Click the `Open` button in the dialog.
4.  **Ready to Use:** The Code Combiner application window should now appear.

## How to Use the Application

**"Run" Tab:**

1.  **Select Input:** Click `Browse...` next to "Codebase Root Directory" and choose the main folder of the code you want to process.
2.  **Select Output:** Click `Save As...` next to "Output Markdown File" and choose where you want to save the combined file (e.g., `my_project_combined.md`).
3.  **Configure (Optional):** Go to the "Settings" tab to adjust included extensions or excluded patterns if needed (see below).
4.  **Combine:** Click the `Combine Codebase` button (it will be enabled once both paths are set).
5.  **Monitor:**
    * Watch the **Progress Bar** and **Current Task** label. Scanning might show an indeterminate progress bar; writing shows progress based on the number of files.
    * See detailed messages in the **Status Log**.
    * The **Est. Chars** label will update after scanning to show the approximate size. You might get a warning popup if it exceeds the threshold set in Settings.
6.  **Cancel (Optional):** Click the `Cancel` button if you need to stop the process early.
7.  **Completion:** A message box will appear on success or failure. The buttons will reset.
8.  **Access Output:** Use the `Open File` or `Open Folder` buttons (now enabled if successful) to quickly access the result.

**"Settings" Tab:**

1.  **Include Extensions:** Edit the comma-separated list of file extensions or exact filenames to include in the output.
2.  **Exclude Patterns:** Edit the list of patterns (one per line) for files or directories to exclude. Uses standard `.gitignore` syntax (e.g., `venv/`, `*.log`, `__pycache__/`).
3.  **Use .gitignore:** Check this box to *also* use rules from a `.gitignore` file found in the selected Codebase Root Directory. (Requires the `python-gitignore` package to be bundled correctly - included in the build steps).
4.  **Warn if Chars >:** Set the character count threshold for the size warning popup.
5.  **Save/Load:** Use `Save Settings Now` to save your changes to `code_combiner_settings.json` (saved automatically on exit too). Use `Reload Saved Settings` to load the last saved configuration.

**Options Menu:**

* Change the **Appearance Mode** (Light/Dark/System) instantly.
* Change the **Color Theme** (Blue/Green/Dark-Blue) - requires an application restart to apply fully.
* **Save Settings Now**.

## Simple Troubleshooting

* **Error: Cannot read file / Permission denied:** The application doesn't have permission to read a specific file/folder, or it might be locked by another program. Check permissions or close other programs using the files.
* **App doesn't open / Crashes Immediately:** Ensure you ran it correctly the first time (bypassing security). Check if antivirus is interfering. Ensure the `.exe` is in a writable location.
* **`.gitignore` not working:** Ensure the "Use .gitignore" box is checked *and* a file named exactly `.gitignore` exists in the selected Codebase Root Directory. The `python-gitignore` library must also be correctly included in the build.
* **Settings not saving:** Make sure the application has permission to write the `code_combiner_settings.json` file in the same directory as `CodeCombiner.exe`.

## For Developers

This section is for those interested in the source code or modifying the tool.

**Setup:**

* Requires Python 3.x (developed with Python 3.10+ recommended).
* Clone or download the source code repository/folder (`File Combine for LLM`).
* Create and activate a Python virtual environment:
    ```bash
    # Navigate to the project directory in your terminal
    cd "path/to/File Combine for LLM"

    # Create virtual environment
    python -m venv venv

    # Activate virtual environment
    # Windows cmd/powershell
    .\venv\Scripts\activate
    # macOS/Linux bash/zsh
    source venv/bin/activate

    # Install dependencies (Create requirements.txt first!)
    # pip freeze > requirements.txt
    pip install -r requirements.txt
    # Or manually: pip install customtkinter python-gitignore
    ```

**Running from Source:**

* Make sure the virtual environment is activated.
* Run the main script:
    ```bash
    python code_combiner.py
    ```
    *(Replace `code_combiner.py` with the actual v1 script name if different, e.g., `gui_code_combiner_v1.py`)*

**Building the Executable (Windows Example using PyInstaller):**

* Ensure PyInstaller is installed (`pip install pyinstaller`).
* Ensure you have an icon file (`checker_icon.ico` used here).
* Find the path to your virtual environment's `customtkinter/assets` folder.
* Run from the project directory with the venv active:
    ```bash
    pyinstaller ^
        --onefile ^
        --windowed ^
        --name="CodeCombiner" ^
        --icon="checker_icon.ico" ^
        --add-data="path/to/your/venv/Lib/site-packages/customtkinter/assets;customtkinter/assets" ^
        gui_code_combiner_v1.py
    ```
    *(Replace paths/filenames. Ensure `python-gitignore` is installed in the venv - PyInstaller should pick it up automatically as it's pure Python. If not, use `--hidden-import=gitignore_parser`)*
* The final executable (`CodeCombiner.exe`) will be in the `dist` folder. Remember to test it thoroughly on a clean machine.
