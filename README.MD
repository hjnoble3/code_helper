# CodeFixer

**CodeFixer** is a Python-based toolset designed to enhance code quality, manage repositories, and interact with Large Language Models (LLMs). It provides functionalities such as identifying unused files, combining repository files, finding and deleting comments, converting naming conventions to snake_case, improving code through formatting and documentation, and analyzing repository structures. Built with extensibility in mind, it leverages libraries like Gradio for an interactive UI and integrates with LLMs for intelligent code analysis and improvements.

## Features

- **LLM Interaction**: Send prompts to an LLM and receive responses for code-related queries.
- **File Checker**: Identify and optionally delete unused files in a repository.
- **File Combiner**: Merge repository files into a single output file based on specified extensions.
- **Comment Finder**: Detect and remove consecutive comments across multiple file types.
- **Snake Case Converter**: Convert camelCase or PascalCase identifiers to snake_case, excluding library-related names.
- **Code Improver**: Enhance code quality with formatting, documentation, and optimization options.
- **Repository Analyzer**: Generate a detailed Markdown tree of the repository structure with file summaries.

## Installation

1. **Clone the Repository**:
```bash
   git clone https://github.com/user/repo.git
   cd repo
```

2. **Run with Docker Compose**:
Ensure you have Docker and Docker Compose installed. The project uses a `docker-compose.yml` file to set up the environment and dependencies. To start the application:
```bash
docker-compose up --build
```

- This command builds the Docker image (including Python 3.8+ and dependencies from `requirements.txt`) and starts the container.
- The `requirements.txt` includes:
  - `requests`: For HTTP requests to the LLM API.
  - `gradio`: For the interactive web interface.
- If using an LLM like LLaMA via Ollama, the `OLLAMA_PORT` environment variable is set in the `docker-compose.yml` (defaults to `11434`).

## Usage

Once the Docker container is running:
- Access the Gradio interface at `http://0.0.0.0:7860` in your browser.
- Use the tabs to interact with different tools, specifying a repository path (default: `/app/shared_files`).

### Example Commands
- **Check Unused Files**: Select a repository path and extensions, then click "Check Unused Files".
- **Combine Files**: Choose extensions and click "Combine Repository Files" to generate `combined_code.txt`.
- **Improve Code**: Select improvement options (e.g., "Add Docstrings") and click "Improve Code".

## Repository Structure

Below is a summary of the repository's structure, detailing key files and directories.

<details>
<summary><b>.</b></summary>

| File | Summary |
| ---- | ------- |
| [docker-compose.yml](https://github.com/user/repo/blob/main/docker-compose.yml) | Defines Docker services for running the Ollama LLM server and Gradio app, including networking, ports (11434 for Ollama, 7860 for Gradio), and volume mappings for persistence and file sharing. |
| [dockerfile](https://github.com/user/repo/blob/main/dockerfile) | Specifies the Docker image build for the Gradio app using Python 3.10-slim, installing system dependencies like `gcc`, copying `requirements.txt` and `src/` contents, and setting the app to run on port 7860. |
| [requirements.txt](https://github.com/user/repo/blob/main/requirements.txt) | This file is a specification for a list of dependencies required to run a Python project, listing the `requests` and `gradio` libraries as necessary. The contents of this file serve to organize and communicate these dependencies to other developers or tools used within the project. |
</details>

<details>
<summary><b>/Other Useful Scripts</b></summary>

| File | Summary |
| ---- | ------- |
| [Otherscripts.md](https://github.com/user/repo/blob/main/Other Useful Scripts/Otherscripts.md) | This file is a Markdown script that provides two separate commands for Git and PowerShell to automate tasks related to version control and file management. The scripts allow users to find the last commit where a specific file was modified and remove empty folders in PowerShell with minimal error handling. |

</details>

<details>
<summary><b>/src</b></summary>

| File | Summary |
| ---- | ------- |
| [__init.py](https://github.com/user/repo/blob/main/src/__init.py) | This script initializes a basic Python application that sets up an instance of the `App` class, which is likely used for data processing or analysis purposes. The script does not provide any specific functionality beyond setting up the base configuration for the application. |
| [camel_case_finder.py](https://github.com/user/repo/blob/main/src/camel_case_finder.py) | This file is a Python script that defines a class called `CamelCaseFinder` which appears to be designed to identify and cache camel case or PascalCase names, particularly in files with extensions such as `. py`, `. js`, `. |
| [code_improver.py](https://github.com/user/repo/blob/main/src/code_improver.py) | This file is a Python script that serves as an implementation of code improvement tools, specifically focusing on formatting, documentation, and optimization for various programming languages and file types. It provides features such as automatically adding comment indicators, style guides, and suggestions for improving code quality based on the specified style guide. |
| [comment_finder.py](https://github.com/user/repo/blob/main/src/comment_finder.py) | This file is a Python script that serves as a comment finder for various programming languages, including Python, TypeScript, JavaScript, Svelte, HTML, and CSS. It reads files from a given directory or specifies a single file and uses regular expressions to identify consecutive comments within each file, storing the results in a dictionary. |
| [file_checker.py](https://github.com/user/repo/blob/main/src/file_checker.py) | This script checks the contents of a specified folder and its subfolders to find any unused files of specified extensions. It recursively collects all files found in each extension's directory and compares their existence within the original folder before determining if they are truly unused. |
| [gradio_interface.py](https://github.com/user/repo/blob/main/src/gradio_interface.py) | This file is a Gradio interface script that allows users to interact with an LLM (Large Language Model) for various tasks such as checking for unused files, combining files, finding and deleting comments, converting to snake_case, improving code quality, or analyzing repository structure. It also includes features like selecting a repository path, providing default value, and displaying error messages when invalid input is provided. |
| [llm_backend.py](https://github.com/user/repo/blob/main/src/llm_backend.py) | This script provides a backend interface to interact with the LLaMA 3 text generation model, allowing users to send prompts and receive generated responses. It uses the `requests` library to send HTTP POST requests to the LLM API, which returns JSON data containing the generated response. |
| [repo_analyzer.py](https://github.com/user/repo/blob/main/src/repo_analyzer.py) | This file's functionality allows users to analyze a repository's structure by generating a markdown tree structure with collapsible directories. The analysis is performed by traversing the repository directory tree starting from a specified path, counting processed files, and building a structured representation of the directories. |
| [repo_file_combiner.py](https://github.com/user/repo/blob/main/src/repo_file_combiner.py) | This file is a Python script that defines a class `RepoFileCombiner` which is designed to combine files from a specified repository into a single output file based on predefined approval rules. |

</details>

</details>



## Contributing

Contributions are welcome! To contribute:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit changes (`git commit -m "Add your feature"`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details (assuming MIT; adjust as needed).

## Contact

For questions or support, reach out via [GitHub Issues](https://github.com/user/repo/issues).