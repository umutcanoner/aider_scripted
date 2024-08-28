import glob
import logging
import os
import random
import subprocess
import sys
from typing import List, Tuple, Union
import threading

import tiktoken

# Configuration Variables

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

"""
Define the PROJECT_DIR constant.

This constant represents the absolute path to the parent directory of the current script's directory.
It is typically used as the root directory for project-related operations.

Note:
    This uses the __file__ attribute, which may not be available in all Python environments.
    In such cases, an alternative method for determining the project root may be needed.

Returns:
    str: The absolute path to the project's root directory.
"""

MANUALLY_ADDED_FILES = [
    os.path.join(PROJECT_DIR, "README.md"),
]
"""
Defines a list of files to be processed regardless of other configurations.

This constant contains file paths that will always be included in the processing,
even if they don't match other filtering criteria. It supports the use of wildcards
for more flexible file selection.

Note:
    - File paths are relative to the PROJECT_DIR.
    - Wildcards like "*.js" or "**/*.md" are supported for pattern matching.
    - These files will be treated as read-only during processing.

Example:
    ["README.md", "docs/*.md", "src/**/*.js"]
"""

PROCESSED_EXTENSIONS = [".js", ".vue", ".scss"]
"""
Define a list of file extensions to be processed by the script.

This constant contains a list of file extensions that the script will consider
when scanning for files to process. Files with these extensions will be included
in the processing workflow.

Note:
    - Extensions should be specified with a leading dot (e.g., ".js").
    - The list can be modified to include or exclude specific file types as needed.

Example:
    [".js", ".vue", ".scss"]
"""

IGNORE_FILES = {
    ".gitignore",
    "**venv*",
    "**node_modules**",
}
"""
Define a set of file patterns to be ignored during file processing.

This constant contains patterns for files and directories that should be
excluded from processing. It supports both exact file names and glob patterns.

Note:
    - Patterns are case-sensitive.
    - '**' matches any number of directories.
    - '*' matches any number of characters within a single directory or file name.

Example patterns:
    - ".gitignore": Ignores the exact file named ".gitignore"
    - "**venv*": Ignores any directory or file containing "venv" at any depth
    - "**node_modules**": Ignores the "node_modules" directory at any depth

Returns:
    set: A set of strings representing file and directory patterns to ignore.
"""

LLM = "default"
"""
Specifies the language model to be used for AI interactions.

This constant determines which AI model will be employed when executing aider commands.
The value "default" indicates that the system should use aider's default model setting.

Other possible values include:
- A specific model name (e.g., "gpt-4", "claude-3")
- "random": Randomly selects a model from the MODELS list for each execution
- "turn-based": Cycles through models in the MODELS list for each execution

Note:
    The actual behavior depends on the implementation of the execute_aider_command function.

See Also:
    MODELS: List of available AI models
    execute_aider_command: Function that uses this LLM setting
"""

MODELS = ["gpt-4o-2024-08-06", "claude-3-5-sonnet-20240620", "chatgpt-4o-latest"]
"""
List of available AI models for language processing tasks.

This constant defines a list of AI model identifiers that can be used
for various natural language processing tasks within the application.

Each string in the list represents a specific AI model version:
- "gpt-4o-2024-08-06": GPT-4 model with a specific version date
- "claude-3-5-sonnet-20240620": Claude 3.5 Sonnet model with a specific version date
- "chatgpt-4o-latest": The latest version of ChatGPT-4

These models can be used in conjunction with the LLM constant to determine
which AI model should be employed for processing tasks.

Note:
    The availability and capabilities of these models may change over time.
    Ensure that the selected model is compatible with the current API and
    has the necessary features for your specific use case.

See Also:
    LLM: Constant that determines which model from this list to use
    execute_aider_command: Function that utilizes these models
"""

EDIT_FORMAT = "diff"
"""
Specifies the edit format to be used when executing aider commands.

This constant determines the format of edits presented by aider when modifying files.
The value "diff" indicates that changes should be displayed in a standard diff format.

Other possible values include:
- "udiff": Unified diff format
- "random": Randomly selects between "diff" and "udiff" for each execution
- "turn-based": Alternates between "diff" and "udiff" for each execution
- "none": No specific edit format is enforced

Note:
    The actual behavior depends on the implementation of the execute_aider_command function.

See Also:
    execute_aider_command: Function that uses this EDIT_FORMAT setting
"""

TOKEN_LIMIT = 4096
"""
Defines the maximum number of tokens allowed for processing.

This constant sets the upper limit for the total number of tokens that can be
processed in a single operation or batch. It is used to prevent exceeding 
memory limits or API constraints when working with large amounts of text.

The value is typically based on the limitations of the AI model or system
being used for text processing.

Note:
    This constant is used in functions like split_files_by_token_limit to
    determine how to group files for processing.

See Also:
    split_files_by_token_limit: Function that uses this token limit
    calculate_token_count: Function for counting tokens in files
"""

# Thread-local storage for tracking the current turn in edit format selection
EDIT_FORMAT_TURN = threading.local()

# Thread-local storage for tracking the current turn in model selection
MODEL_TURN = threading.local()


# Function to initialize turn counters for edit format and model selection
def initialize_turns():
    # Reset the edit format turn counter to 0
    EDIT_FORMAT_TURN.value = 0

    # Reset the model selection turn counter to 0
    MODEL_TURN.value = 0


# Reset turn counters for edit format and model selection
# This ensures a fresh start for each execution of the script
initialize_turns()

SCAN_START = ""
"""
Defines the starting point for file scanning within the project directory.

This constant specifies the subdirectory within PROJECT_DIR from which to begin
scanning for files to process. An empty string indicates that scanning should
start from the PROJECT_DIR itself.

Note:
    - The path is relative to PROJECT_DIR.
    - An empty string means start from the project root.
    - Use forward slashes for cross-platform compatibility (e.g., "src/main").

Example:
    "src/components" would start scanning from the 'components' folder inside 'src'.
"""

SCAN_DEPTH = 0
"""
Define the maximum depth for directory scanning.

This constant determines how deep the file scanner will traverse into subdirectories
when looking for files to process. A value of 0 means there is no limit, and all
subdirectories will be scanned.

Values:
    0: No depth limit (scan all subdirectories)
    n: Positive integer representing the maximum number of subdirectory levels to scan

Note:
    This constant works in conjunction with SCAN_START to determine which files
    are included in the processing.

See Also:
    SCAN_START: The starting point for file scanning
    get_files_to_process: Function that uses this depth limit
"""

SCAN_LOGIC = "standard"
"""
Defines the scanning logic to be used for processing files.

This constant determines the strategy used for scanning and processing files
within the project. It affects how files are grouped, processed, and whether
dependencies are considered.

Possible values:
- "basic": Process each file individually without considering dependencies.
- "standard": Group files based on token limits and process them in batches.
- "basic_dependency-cruiser": Process each file individually, considering its dependencies. map-tokens: 0 recommended.
- "standard_dependency-cruiser": Group files and process them in batches, considering dependencies. map-tokens: 0 recommended.

The chosen logic impacts the behavior of the `process_files` function.

See Also:
    process_files: Function that uses this SCAN_LOGIC setting
    process_basic, process_standard, process_basic_dependency_cruiser, 
    process_standard_dependency_cruiser: Specific processing functions for each logic
"""

MESSAGES = [
    "Update API_DOCUMENTATION.md using the supplied files without being repetitive. Assume the supplied files are correct.",
    "Enrich API_DOCUMENTATION.md using the supplied files without being repetitive. Assume the supplied files are correct.",
]
"""
Defines a list to store messages for processing.

This constant is initialized as an empty list and is intended to be populated
with messages that will be used during file processing operations. The specific
content and format of these messages depend on the implementation details of
the processing functions.

See Also:
    execute_aider_command: Function that uses messages from this list
    process_files: Function that indirectly uses these messages
"""

DRY_RUN = False
"""
Flag to enable or disable dry run mode.

When set to True, the script will simulate execution without making actual changes.
This is useful for testing and debugging purposes. When False, the script will
perform actual file processing and modifications.

Note:
    This constant affects the behavior of various functions throughout the script,
    particularly those involved in file processing and aider command execution.

See Also:
    execute_aider_command: Function that checks this flag before executing commands
    log_aider_command: Function called when this flag is True to log dry run information
"""

DEBUG = True
"""
Enables or disables the debug mode for logging purposes.

When set to True, the logging is configured to display debug-level messages,
providing detailed output for troubleshooting. When False, the logging level is set
to info, which provides less verbose output. 

Note:
    This constant is used when setting up the logging configuration.

See Also:
    logging.basicConfig: Function that utilizes this DEBUG setting for log level configuration
"""

# Set up logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def debug_log(message):
    """
    Logs a debug message if debugging is enabled.

    This function checks the global DEBUG flag and logs the provided
    message at the debug level if debugging is enabled. This allows for
    conditional logging of detailed output for development and troubleshooting.

    Args:
        message: The message string to be logged.

    Returns:
        None

    Raises:
        This function does not raise any exceptions.

    See Also:
        logger: The logger object used for logging messages.
    """
    if DEBUG:
        logger.debug(message)


def calculate_token_count(files: List[str]) -> int:
    """
    Calculate the total number of tokens in the given files using tiktoken.

    This function iterates through the list of file paths provided, reads their
    contents, and calculates the total token count using the tiktoken library with
    the "cl100k_base" encoding. It returns the sum of token counts for all specified files.

    Args:
        files (List[str]): A list of file paths for which token counts need to be calculated.

    Returns:
        int: The total token count across all files.

    Raises:
        Exception: Logs an error if any file fails to process due to reading issues or encoding problems.
    """
    debug_log(f"Calculating token count for {len(files)} files")
    enc = tiktoken.get_encoding("cl100k_base")
    total_tokens = 0
    for file in files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()
            file_tokens = len(enc.encode(content.strip()))
            total_tokens += file_tokens
            debug_log(f"File: {file}, Tokens: {file_tokens}")
        except Exception as e:
            logger.error(f"Error processing file {file}: {e}")
    debug_log(f"Total tokens: {total_tokens}")
    return total_tokens


def get_files_to_process() -> List[str]:
    """
    Collects a list of files to be processed based on project-specific rules.

    This function scans the project directory starting from a specified subdirectory and
    collects all files with extensions that match the configured processed extensions.
    It excludes any files that match the specified ignore patterns. Additionally, it
    includes any manually added files even if they don't match the processed extensions.

    Returns:
        List[str]: A list of absolute file paths that meet the processing criteria.

    Raises:
        This function does not explicitly raise any exceptions but will propagate any
        exceptions raised by underlying calls, such as issues with file reading or
        path manipulations.
    """
    files = []
    scan_start_path = os.path.join(PROJECT_DIR, SCAN_START)
    for root, _, filenames in os.walk(scan_start_path):
        relative_path = os.path.relpath(root, scan_start_path)
        current_depth = len(relative_path.split(os.sep)) - 1
        if SCAN_DEPTH > 0 and current_depth > SCAN_DEPTH:
            continue
        for filename in filenames:
            if any(filename.endswith(ext) for ext in PROCESSED_EXTENSIONS):
                file_path = os.path.join(root, filename)
                relative_file_path = os.path.relpath(file_path, PROJECT_DIR)
                if not any(
                    glob.fnmatch.fnmatch(relative_file_path, pattern)
                    for pattern in IGNORE_FILES
                ):
                    files.append(file_path)

    # Add manually added files
    for file_pattern in MANUALLY_ADDED_FILES:
        for file_path in glob.glob(
            os.path.join(PROJECT_DIR, file_pattern), recursive=True
        ):
            relative_file_path = os.path.relpath(file_path, PROJECT_DIR)
            if os.path.isfile(file_path) and not any(
                glob.fnmatch.fnmatch(relative_file_path, pattern)
                for pattern in IGNORE_FILES
            ):
                files.append(file_path)

    return list(set(files))  # Remove duplicates


def get_dependencies(files: List[str]) -> List[str]:
    """
    Get dependencies for a list of files using dependency-cruiser.

    This function first filters the given list of files to include only those with valid
    extensions for dependency-cruiser processing. It then uses dependency-cruiser to
    discover and return a list of dependencies for the filtered files.

    Args:
        files (List[str]): A list of file paths for which dependencies need to be identified.

    Returns:
        List[str]: A list of file paths representing the dependencies for the input files.
                   Returns an empty list if no dependencies are found or if input is empty.

    Notes:
        This function relies on the presence of dependency-cruiser, and it assumes the tool
        is installed and available in the system's execution path. It internally uses
        `filter_files_for_dependency_cruiser` and `run_dependency_cruiser` to perform
        filtering and dependency extraction, respectively.

    See Also:
        filter_files_for_dependency_cruiser: Helper function to filter files for valid extensions.
        run_dependency_cruiser: Executes dependency-cruiser to extract dependencies.
    """
    if not files:
        return []

    filtered_files = filter_files_for_dependency_cruiser(files)
    if not filtered_files:
        return []

    return run_dependency_cruiser(filtered_files)


def filter_files_for_dependency_cruiser(
    files: List[Union[str, List[str]]]
) -> List[str]:
    """
    Filters a list of files to retain only those with extensions valid for dependency-cruiser.

    Valid extensions are provided as a tuple and include file types commonly used with dependency-cruiser.

    Args:
        files (List[Union[str, List[str]]]): A list of file paths or nested lists of file paths to filter.

    Returns:
        List[str]: A list of file paths that have a valid extension for dependency-cruiser.

    Raises:
        This function does not explicitly raise any exceptions but logs a warning if no valid files are found.
    """
    valid_extensions = (".js", ".ts", ".jsx", ".vue")

    def is_valid_file(file):
        """
        Determines if the given file has a valid extension for processing.

        This function checks if the provided file is a string and whether
        it ends with an extension from the valid_extensions list.

        Args:
            file: The file path to check, expected to be a string.

        Returns:
            bool: True if the file is a string ending with one of the valid
            extensions; False otherwise.

        Raises:
            This function does not explicitly raise any exceptions.
        """
        return isinstance(file, str) and file.lower().endswith(valid_extensions)

    filtered_files = []
    for file in files:
        if isinstance(file, list):
            filtered_files.extend([f for f in file if is_valid_file(f)])
        elif is_valid_file(file):
            filtered_files.append(file)

    if not filtered_files:
        logger.warning("No valid files for dependency-cruiser to process.")

    return filtered_files


def run_dependency_cruiser(files: List[str]) -> List[str]:
    """
    Executes the dependency-cruiser tool on a list of specified files and
    processes the output to extract file dependencies.

    This function constructs a command to run dependency-cruiser, executes it,
    and processes the stdout to extract dependencies. It logs errors if the
    command execution fails or if the tool is not found.

    Args:
        files (List[str]): A list of file paths on which to run dependency-cruiser.

    Returns:
        List[str]: A list of file dependencies identified by dependency-cruiser.

    Raises:
        subprocess.CalledProcessError: If the subprocess running dependency-cruiser
                                        encounters an error.
        FileNotFoundError: If the dependency-cruiser tool is not found in the system PATH.

    See Also:
        process_dependency_cruiser_output: A helper function used to process the raw output.
        log_dependency_cruiser_results: Logs results of the dependency extraction process.
    """
    dependency_cruiser_cmd = "npx.cmd" if sys.platform == "win32" else "npx"

    cmd = [
        dependency_cruiser_cmd,
        "dependency-cruiser",
        "--no-config",
        "--exclude",
        "node_modules",
        "-T",
        "text",
    ] + files

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw_output = result.stdout.strip().splitlines()
        dependencies = process_dependency_cruiser_output(raw_output)
        log_dependency_cruiser_results(raw_output, dependencies)
        return dependencies
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running dependency-cruiser: {e}")
        logger.error(
            "Please ensure dependency-cruiser is installed and in your system PATH."
        )
        logger.error("You can install it by running: npm install -g dependency-cruiser")
    except FileNotFoundError:
        logger.error(
            "Error: dependency-cruiser not found. Please install it and ensure it's in your system PATH."
        )
        logger.error("You can install it by running: npm install -g dependency-cruiser")

    return []


def process_dependency_cruiser_output(raw_output: List[str]) -> List[str]:
    """
    Processes and extracts dependencies from the given raw output of dependency-cruiser.

    This function takes in raw output strings from the dependency-cruiser tool and extracts
    the dependencies using predefined markers. It handles decoding and processing of lines to
    ensure valid dependency pairs are identified. Any issues with malformed lines will result
    in warnings being logged.

    Args:
        raw_output (List[str]): The raw lines of output as strings from the dependency-cruiser tool.

    Returns:
        List[str]: A list of unique dependencies extracted from the input, retaining order for compatibility.

    Raises:
        ValueError: Issues related to malformed lines or invalid source/target pairs are logged as warnings.
    """
    logger.debug("Entering method: process_dependency_cruiser_output")

    if not raw_output:
        logger.warning("Empty raw output from dependency-cruiser.")
        return []

    dependencies = set()  # Use a set to avoid duplicates
    logger.debug(
        f"Raw output from dependency-cruiser received: {len(raw_output)} lines"
    )

    for line in raw_output:
        line_clean = line.encode("utf-8", "ignore").decode("utf-8")
        logger.debug(f"Processing line: {line_clean}")

        # Handle non-standard or malformed lines using safer regex or string matching
        try:
            if " → " in line_clean or " â†’ " in line_clean:
                arrow = " â†’ " if " â†’ " in line_clean else " → "
                source, target = map(str.strip, line_clean.rsplit(arrow, 1))
                if source and target:
                    dependencies.update([source, target])
                    logger.debug(
                        f"Extracted dependency pair: (source: {source}, target: {target})"
                    )
                else:
                    raise ValueError(
                        f"Invalid source/target pair: source='{source}', target='{target}'"
                    )
            else:
                raise ValueError(
                    f"Line did not contain the valid arrow separator: {line_clean}"
                )
        except ValueError as ve:
            logger.warning(f"Failed to process line: {ve}")

    sanitized_output = list(
        dependencies
    )  # Convert back to list to preserve API compatibility
    if sanitized_output:
        debug_log(f"Sanitized dependency-cruiser output: {sanitized_output}")
    else:
        logger.warning("No valid dependencies found in the dependency-cruiser output.")

    logger.debug("Exiting method: process_dependency_cruiser_output")
    return sanitized_output


def log_dependency_cruiser_results(raw_output: List[str], sanitized_output: List[str]):
    """
    Logs the results of the dependency-cruiser processing if in DRY_RUN mode.

    This function checks if the DRY_RUN flag is enabled and, if so, writes the raw and
    sanitized output of the dependency-cruiser tool to a log file. It handles potential
    encoding issues by safely converting lines to ASCII if necessary.

    Args:
        raw_output (List[str]): The raw output from the dependency-cruiser tool.
        sanitized_output (List[str]): The processed and cleaned list of dependencies as
            identified by the dependency-cruiser tool.

    Raises:
        UnicodeEncodeError: Catches any Unicode encoding errors during log writing,
            encoding problematic lines into ASCII-compatible representation as a fallback.
    """
    if DRY_RUN:
        log_file_path = os.path.join(os.path.dirname(__file__), "aider_all_dry_run.log")
        with open(log_file_path, "a", encoding="utf-8") as log_file:
            log_file.write("Raw dependency-cruiser output:\n")
            for line in raw_output:
                try:
                    log_file.write(line + "\n")
                except UnicodeEncodeError:
                    log_file.write(
                        line.encode("ascii", "replace").decode("ascii") + "\n"
                    )
            log_file.write("Sanitized dependency-cruiser output:\n")
            for line in sanitized_output:
                try:
                    log_file.write(line + "\n")
                except UnicodeEncodeError:
                    log_file.write(
                        line.encode("ascii", "replace").decode("ascii") + "\n"
                    )


def execute_aider_command(files: List[str], read_only_files: List[str], message: str):
    """
    Executes the aider command to process or modify files.

    This function determines the appropriate model and edit format to use for the aider
    command based on configuration settings. It constructs the command with specified
    files and messages, logging the command if in dry run mode, or executing it otherwise.

    Args:
        files (List[str]): List of file paths to be included in processing.
        read_only_files (List[str]): List of file paths to be read-only during processing.
        message (str): A formatted message to accompany the aider command execution.

    Raises:
        Exception: Logs any unexpected errors encountered during aider command execution.
    """
    global EDIT_FORMAT_TURN, MODEL_TURN
    model = None
    if LLM == "random":
        model = random.choice(MODELS)
    elif LLM == "turn-based":
        model = MODELS[MODEL_TURN % len(MODELS)]
        MODEL_TURN += 1
    # For "default", we don't set a model, using aider's default

    if EDIT_FORMAT == "random":
        edit_format = random.choice(["diff", "udiff"])
    elif EDIT_FORMAT == "turn-based":
        edit_format = "diff" if EDIT_FORMAT_TURN % 2 == 0 else "udiff"
        EDIT_FORMAT_TURN += 1
    else:
        edit_format = EDIT_FORMAT

    cmd = ["aider"]
    if model:
        cmd.extend(["--model", model])
    if edit_format != "none":
        cmd.extend(["--edit-format", edit_format])

    for file in MANUALLY_ADDED_FILES + read_only_files:
        cmd.extend(["--read", file])
    for file in files:
        cmd.extend(["--file", file])

    cmd.extend(
        [
            "--message",
            message.format(
                file_list=", ".join(files), read_list=", ".join(read_only_files)
            ),
        ]
    )

    if DRY_RUN:
        log_aider_command(cmd, model, edit_format, message, read_only_files, files)
    else:
        try:
            logger.info(f"Executing aider command: {' '.join(cmd)}")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            while True:
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output:
                    logger.info(output.strip())

            return_code = process.poll()

            if return_code == 0:
                logger.info("Aider command executed successfully")
            else:
                error_output = process.stderr.read()
                logger.error(
                    f"Error executing aider command. Return code: {return_code}"
                )
                logger.error(f"Error output: {error_output}")
        except Exception as e:
            logger.error(f"Unexpected error executing aider command: {e}")


def log_aider_command(
    cmd: List[str],
    model: str,
    edit_format: str,
    message: str,
    read_only_files: List[str],
    files: List[str],
):
    """
    Logs the details of the aider command execution to a log file.

    This function records the full command, the model used, the edit format, and
    details about the read-only and processed files. It also logs the token counts
    for the processed and read-only files along with the token limit.

    Args:
        cmd (List[str]): The full aider command as a list of strings to be logged.
        model (str): The name of the language model being used. Defaults to "Default"
            if no specific model is assigned.
        edit_format (str): The format in which edits are to be displayed.
        message (str): The message associated with the aider command execution.
        read_only_files (List[str]): List of files that are to be treated as read-only.
        files (List[str]): List of files that are to be processed.

    Raises:
        This function does not explicitly raise any exceptions
        but may propagate exceptions from underlying file operations.
    """
    log_file_path = os.path.join(os.path.dirname(__file__), "aider_all_dry_run.log")
    with open(log_file_path, "a", encoding="utf-8") as log_file:
        log_file.write("=" * 80 + "\n")
        log_file.write(f"Aider Command Execution\n")
        log_file.write("=" * 80 + "\n")
        log_file.write(f"Command: {' '.join(cmd)}\n")
        log_file.write(f"Model: {model or 'Default'}\n")
        log_file.write(f"Edit Format: {edit_format}\n")
        log_file.write(f"Message: {message}\n")
        log_file.write(f"Read-only files ({len(read_only_files)}):\n")
        for file in read_only_files:
            log_file.write(f"  - {file}\n")
        log_file.write(f"Files to process ({len(files)}):\n")
        for file in files:
            log_file.write(f"  - {file}\n")
        log_file.write(f"Token count (files): {calculate_token_count(files)}\n")
        log_file.write(
            f"Token count (read-only): {calculate_token_count(read_only_files)}\n"
        )
        total_tokens = calculate_token_count(files + read_only_files)
        log_file.write(f"Total token count: {total_tokens}\n")
        log_file.write(f"Token limit: {TOKEN_LIMIT}\n")
        log_file.write(f"Remaining tokens: {TOKEN_LIMIT - total_tokens}\n")
        log_file.write("\n")


def split_files_by_token_limit(
    files: List[str], token_limit: int
) -> Tuple[List[List[str]], List[str]]:
    """
    Split the input files into groups based on the token limit.

    This function organizes files into groups where each group's total token count
    does not exceed the provided token limit. It also identifies files that
    individually exceed the token limit, marking them for separate processing.

    Parameters:
        files (List[str]): A list of file paths to be organized based on token count.
        token_limit (int): The maximum number of tokens allowed per group of files.

    Returns:
        Tuple[List[List[str]], List[str]]: A tuple where the first element is a list
        of file groups each within the token limit, and the second element is a list
        of files that individually exceed the token limit.

    Raises:
        This function does not explicitly raise any exceptions but will log a warning
        for any file that exceeds the token limit.
    """
    file_groups = []
    current_group = []
    current_tokens = 0
    oversized_files = []

    for file in files:
        file_tokens = calculate_token_count([file])
        if file_tokens > token_limit:
            # Handle files that individually exceed the token limit
            logger.warning(
                f"File {file} exceeds token limit ({file_tokens} > {token_limit}). It will be processed individually."
            )
            oversized_files.append(file)
            if current_group:
                file_groups.append(current_group)
                current_group = []
                current_tokens = 0
        elif current_tokens + file_tokens > token_limit:
            # Start a new group if adding this file would exceed the limit
            if current_group:
                file_groups.append(current_group)
            current_group = [file]
            current_tokens = file_tokens
        else:
            # Add the file to the current group
            current_group.append(file)
            current_tokens += file_tokens

    if current_group:
        file_groups.append(current_group)

    # Handle the case where a single file exceeds the token limit
    if not file_groups and len(oversized_files) == 1:
        file_groups.append(oversized_files)
        oversized_files = []

    return file_groups, oversized_files


def process_files(files_to_process: List[str], read_only_files: List[str]):
    """
    Process files according to the specified scanning logic.

    This function dispatches file processing tasks to one of several specific
    processing functions based on the global SCAN_LOGIC setting. It supports
    different strategies, such as processing each file individually or grouping
    files with or without considering dependencies.

    Parameters:
        files_to_process (List[str]): A list of file paths to process. These files
        are candidates for modification or analysis.

        read_only_files (List[str]): A list of file paths intended to provide
        read-only context during processing. They should not be modified.

    Raises:
        Does not explicitly raise exceptions, but will log errors if the
        SCAN_LOGIC setting is invalid or unsupported.

    See Also:
        process_basic: Function for basic individual file processing.
        process_standard: Function for processing files in groups.
        process_basic_dependency_cruiser: Function for basic processing with
        dependency consideration.
        process_standard_dependency_cruiser: Function for grouped processing
        with dependency consideration.
    """
    logger.info(
        f"Processing {len(files_to_process)} files with {len(read_only_files)} read-only files"
    )

    if SCAN_LOGIC == "basic":
        process_basic(files_to_process, read_only_files)
    elif SCAN_LOGIC == "standard":
        process_standard(files_to_process, read_only_files)
    elif SCAN_LOGIC == "basic_dependency-cruiser":
        process_basic_dependency_cruiser(files_to_process, read_only_files)
    elif SCAN_LOGIC == "standard_dependency-cruiser":
        process_standard_dependency_cruiser(files_to_process, read_only_files)
    else:
        logger.error(f"Invalid SCAN_LOGIC: {SCAN_LOGIC}")


def process_basic(files_to_process: List[str], read_only_files: List[str]):
    """
    Processes each file individually using the aider command.

    This function iterates over a list of files to process, executing the aider command
    on each one individually. During each execution, read-only files are included for context,
    and a randomly selected message is supplied from a predefined list.

    Args:
        files_to_process (List[str]): List of file paths to be processed individually.
        read_only_files (List[str]): List of file paths to be treated as read-only for context.

    Raises:
        The function implicitly relies on execute_aider_command, which may raise exceptions
        related to command execution errors. It does not handle these exceptions internally,
        so any exceptions will propagate to the caller.
    """
    for file in files_to_process:
        execute_aider_command([file], read_only_files, random.choice(MESSAGES))


def process_standard(files_to_process: List[str], read_only_files: List[str]):
    """
    Processes files in groups based on a token limit, executing the aider command.

    This function collects files into groups where each group's total token count is within
    the defined token limit. It then processes each group using the aider command. For files
    that individually exceed the token limit, it processes them separately, issuing a warning.

    Args:
        files_to_process (List[str]): List of file paths intended for processing.
        read_only_files (List[str]): List of file paths that should remain read-only during processing.

    Raises:
        This function might propagate exceptions from the execute_aider_command function.
    """
    file_groups, oversized_files = split_files_by_token_limit(
        files_to_process, TOKEN_LIMIT
    )

    for file_group in file_groups:
        execute_aider_command(file_group, read_only_files, random.choice(MESSAGES))

    for file in oversized_files:
        logger.warning(f"Processing oversized file: {file}")
        execute_aider_command([file], read_only_files, random.choice(MESSAGES))


def process_basic_dependency_cruiser(
    files_to_process: List[str], read_only_files: List[str]
):
    """
    Processes each file individually with dependency consideration.

    This function uses the dependency-cruiser to find dependencies for each file
    in the files_to_process list. It includes these dependencies as part of the
    read-only context during processing. The processed files are executed using
    the aider command, with a randomly selected message from a predefined list.

    Parameters:
        files_to_process (List[str]): A list of file paths to process individually.
        read_only_files (List[str]): A list of file paths intended to remain read-only
        during processing but to be included for context.

    Raises:
        The function relies on execute_aider_command, which may raise exceptions
        related to command execution errors. These are not handled within this
        function, so will propagate to the caller.
    """
    for file in files_to_process:
        dependencies = get_dependencies([file])
        all_read_only = list(set(read_only_files + dependencies))
        execute_aider_command([file], all_read_only, random.choice(MESSAGES))


def process_standard_dependency_cruiser(
    files_to_process: List[str], read_only_files: List[str]
):
    """
    Processes files in groups while considering file dependencies.

    This function collects files into groups where each group's total
    token count is within the defined token limit. It finds dependencies
    for each group of files using the dependency-cruiser tool. It processes
    each group, including dependencies and read-only files as context during
    execution, using the aider command.

    Parameters:
        files_to_process (List[str]): A list of file paths intended
        for processing.

        read_only_files (List[str]): A list of file paths that should
        remain read-only during processing.

    Raises:
        This function may propagate exceptions from the get_dependencies
        or execute_aider_command functions if any errors occur during
        dependency extraction or command execution.
    """
    file_groups, oversized_files = split_files_by_token_limit(
        files_to_process, TOKEN_LIMIT
    )

    for file_group in file_groups:
        dependencies = get_dependencies(file_group)
        all_read_only = list(set(read_only_files + dependencies))
        execute_aider_command(file_group, all_read_only, random.choice(MESSAGES))

    for file in oversized_files:
        logger.warning(f"Processing oversized file: {file}")
        dependencies = get_dependencies([file])
        all_read_only = list(set(read_only_files + dependencies))
        execute_aider_command([file], all_read_only, random.choice(MESSAGES))


def main():
    """
    Main execution function for processing files within the project.

    This function orchestrates the file processing workflow based on configuration
    settings like DRY_RUN and SCAN_LOGIC. It manages the collection of files to
    process, invokes the processing logic, and logs the results or execution details.

    If DRY_RUN is enabled, the function also compiles a summary log detailing
    file processing projections and statistics, which is written to a log file.

    The function handles any exceptions that occur during execution by logging the
    error and exception details for troubleshooting purposes.

    Raises:
        Exception: If any unforeseen errors occur during execution, they are logged
        along with the full exception details.
    """
    try:
        log_file_path = os.path.join(os.path.dirname(__file__), "aider_all_dry_run.log")
        log_content = []

        if DRY_RUN:
            log_content.extend(
                [
                    "Dry Run Log\n\n",
                    f"Project Directory: {PROJECT_DIR}\n",
                    f"Scan Start: {SCAN_START}\n",
                    f"Scan Depth: {SCAN_DEPTH}\n",
                    f"Scan Logic: {SCAN_LOGIC}\n",
                    f"LLM: {LLM}\n",
                    f"Edit Format: {EDIT_FORMAT}\n",
                    f"Token Limit: {TOKEN_LIMIT}\n\n",
                ]
            )

        files_to_process = get_files_to_process()
        read_only_files = MANUALLY_ADDED_FILES.copy()

        process_files(files_to_process, read_only_files)

        if DRY_RUN:
            log_content.extend(
                [
                    "=" * 80 + "\n",
                    "Dry Run Summary:\n",
                    "=" * 80 + "\n",
                    f"Total files processed: {len(files_to_process)}\n",
                    f"Total read-only files: {len(read_only_files)}\n",
                    f"Total token count: {calculate_token_count(files_to_process + read_only_files)}\n",
                    "\nProcessed file extensions:\n",
                ]
            )
            for ext in PROCESSED_EXTENSIONS:
                count = sum(1 for f in files_to_process if f.endswith(ext))
                log_content.append(f"  {ext}: {count}\n")

            with open(log_file_path, "w", encoding="utf-8") as log_file:
                log_file.writelines(log_content)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        logger.exception("Exception details:")


if __name__ == "__main__":
    main()
