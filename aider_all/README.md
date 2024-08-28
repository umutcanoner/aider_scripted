# Script for Aider Command Line Utility

## Overview

This project is a command-line utility designed to automate file processing tasks using AI models and custom processing logic. The script scans a project directory for specific files, processes them based on defined rules, and can execute commands that interact with AI models like OpenAI's GPT or Anthropic's Claude. It supports various configurations for file scanning, dependency management, and AI model selection.

It is very useful for generating API documentation, codebase refactoring, and other tasks that require processing multiple files in a project. The script can be customized to work with different file types, AI models, and processing strategies.

## Key Features

- **Customizable File Scanning**: Define which files to process based on extensions and patterns. Supports depth-limited directory traversal.
- **AI Model Integration**: Interact with AI models such as GPT-4, Claude, and ChatGPT to process and modify files.
- **Dependency Management**: Automatically detects and includes file dependencies using `dependency-cruiser`.
- **Token Limit Management**: Files are grouped according to token limits, ensuring that processing stays within manageable bounds.
- **Debug and Dry Run Modes**: Provides detailed debug logging and a dry run mode for testing without making changes.
- **Flexible Execution Logic**: Choose between various processing strategies, including individual file processing and batch processing.

## Installation

### Prerequisites

- Python 3.7 or higher
- `pip` (Python package manager)
- Node.js and `npm` for `dependency-cruiser` (only if you plan to use dependency management)
- Required Python libraries:
  - `tiktoken`
  - `glob`
  - `os`
  - `subprocess`
  - `logging`
  - `random`
  - `threading`

### Setup

1. **Clone the script**:

2. **Install dependencies**:

3. **Install `dependency-cruiser`** (if needed):

   ```bash
   npm install -g dependency-cruiser
   ```

## Usage

### Configuration

The script is highly configurable through several constants defined at the top of the script:

- **`PROJECT_DIR`**: The root directory where the script will start scanning for files.
- **`PROCESSED_EXTENSIONS`**: List of file extensions to be included in the processing.
- **`IGNORE_FILES`**: Patterns for files and directories that should be excluded from processing.
- **`LLM`**: Specifies the AI model to use (`default`, `random`, `turn-based`).
- **`MODELS`**: List of available AI models for processing.
- **`EDIT_FORMAT`**: Determines the edit format for processing (`diff`, `udiff`, `random`, `turn-based`, `none`).
- **`TOKEN_LIMIT`**: Maximum number of tokens allowed for processing in one batch.
- **`SCAN_START`**: Subdirectory within `PROJECT_DIR` to begin scanning.
- **`SCAN_DEPTH`**: Maximum depth for directory scanning.
- **`SCAN_LOGIC`**: Determines the file processing strategy (`basic`, `standard`, `basic_dependency-cruiser`, `standard_dependency-cruiser`).
- **`DRY_RUN`**: Flag for simulating execution without making actual changes.
- **`DEBUG`**: Flag to enable or disable debug mode.

### Running the Script

1. **Basic Run**:
   Simply execute the script to start processing files according to the configuration:

   ```bash
   python aider_all.py
   ```

2. **Dry Run Mode**:
   To simulate the process without making any changes, enable `DRY_RUN` in the script:

   ```python
   DRY_RUN = True
   ```

   Then run:

   ```bash
   python aider_all.py
   ```

3. **Debug Mode**:
   Enable detailed logging by setting `DEBUG` to `True`:

   ```python
   DEBUG = True
   ```

   Then run the script to see detailed logs in the console:

   ```bash
   python aider_all.py
   ```

### Example Scenarios

#### Scenario 1: Process All JavaScript Files

To process all `.js` files in the project root and its subdirectories:

- Set `PROCESSED_EXTENSIONS` to `[".js"]`.
- Run the script:

  ```bash
  python aider_all.py
  ```

#### Scenario 2: Use Dependency-Cruiser for Dependency-Aware Processing

To process files with consideration of their dependencies:

- Set `SCAN_LOGIC` to `"standard_dependency-cruiser"`.
- Ensure `dependency-cruiser` is installed.
- Run the script:

  ```bash
  python aider_all.py
  ```

## Logging and Debugging

The script logs its actions based on the `DEBUG` and `DRY_RUN` settings:

- **Debug Logs**: Enable detailed logging by setting `DEBUG = True`. Logs will include detailed information about file processing steps.
- **Dry Run Logs**: If `DRY_RUN` is enabled, the script will write a detailed log of what would have been processed to `aider_all_dry_run.log`.

## Miscellaneous

- Function comments and docstrings are for your reference. They might impair your experience, I suggest you remove them after you understand the script.
