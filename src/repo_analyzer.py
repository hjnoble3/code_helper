# repo_analyzer.py
import json
import os
import datetime
from typing import Dict, Tuple, List
from llm_backend import llm_interface


class RepoAnalyzer:
    def __init__(self, github_base_url: str, cache_file: str = 'processed_files.json'):
        self.cache_file = cache_file
        self.processed_files = self.load_cache()
        self.github_base_url = github_base_url

    def load_cache(self) -> Dict:
        """Load the cache file if it exists."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading cache: {e}")
        return {}

    def save_cache(self) -> None:
        """Save the current cache to file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.processed_files, f, indent=2)
        except IOError as e:
            print(f"Error saving cache: {e}")

    def generate_tree(self, startpath: str, extensions: List[str], model: str) -> Tuple[str, int]:
        """Generate the markdown tree structure with collapsible directories."""
        if not os.path.exists(startpath):
            return f"The path '{startpath}' does not exist.", 0

        tree = ["## 📂 Repository Structure\n\n"]
        processed_files_count = 0
        allowed_extensions = tuple(f".{ext}" if not ext.startswith('.') else ext for ext in extensions)

        # Build directory structure
        dir_structure = {}
        queue = [(startpath, None)]

        while queue:
            current_path, parent = queue.pop(0)
            files = []
            dirs = []

            try:
                for item in os.listdir(current_path):
                    full_path = os.path.join(current_path, item)
                    if os.path.isfile(full_path) and item.endswith(allowed_extensions) and not item.startswith('.'):
                        files.append(item)
                    elif os.path.isdir(full_path) and not item.startswith('.') and item != 'node_modules':
                        dirs.append(item)
                        queue.append((full_path, current_path))
            except Exception as e:
                print(f"Error accessing directory {current_path}: {e}")
                continue

            dir_structure[current_path] = {
                'files': files,
                'parent': parent,
                'name': os.path.basename(current_path) if current_path != startpath else '.'
            }

        def process_files(path: str, files: List[str]) -> str:
            nonlocal processed_files_count
            table_rows = []

            for f in sorted(files):
                filepath = os.path.join(path, f)
                relative_path = os.path.relpath(filepath, startpath)
                cache_key = f"{startpath}:{relative_path}"

                try:
                    if cache_key in self.processed_files:
                        summary = self.processed_files[cache_key]['summary']
                    else:
                        print(f"Processing {relative_path}...")
                        summary = self.analyze_file(filepath, model)
                        if summary and "Error" not in summary:
                            self.processed_files[cache_key] = {
                                'summary': summary,
                                'processed_at': datetime.datetime.now().isoformat()
                            }
                            self.save_cache()
                            processed_files_count += 1

                    github_path = relative_path.replace(os.sep, '/')
                    github_url = f"{self.github_base_url.rstrip('/')}/{github_path}"
                    emoji = self.get_file_emoji(f)

                    table_rows.append(f"| [{f}]({github_url}) | {summary} |\n")
                except Exception as e:
                    print(f"Error processing file {f}: {e}")

            if table_rows:
                return (
                    "| File | Summary |\n"
                    "| ---- | ------- |\n" +
                    "".join(table_rows) + "\n"
                )
            return ""

        def process_directory(path: str, level: int = 0) -> None:
            data = dir_structure[path]
            dir_name = '.' if path == startpath else f"{os.path.sep}{os.path.relpath(path, startpath).replace(os.sep, '/')}"
            tree.append("<details>\n")
            tree.append(f"<summary><b>{dir_name}</b></summary>\n\n")

            files_output = process_files(path, data['files'])
            if files_output:
                tree.append(files_output)

            subdirs = sorted([p for p, d in dir_structure.items() if d['parent'] == path], key=lambda x: dir_structure[x]['name'])
            for subdir in subdirs:
                process_directory(subdir, level + 1)

            tree.append("</details>\n\n")

        process_directory(startpath)
        return "".join(tree), processed_files_count

    def get_file_emoji(self, filename: str) -> str:
        """Return an appropriate emoji for the file type (unused in new format but kept for compatibility)."""
        ext = os.path.splitext(filename)[1].lower()
        emoji_map = {
            '.py': '![Python](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg){: width=40 height=40}',
            '.js': '![JavaScript](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/javascript/javascript-original.svg){: width=40 height=40}',
            '.ts': '![TypeScript](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/typescript/typescript-original.svg){: width=40 height=40}',
            '.tsx': '![React](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/react/react-original.svg){: width=40 height=40}',
            '.jsx': '![React](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/react/react-original.svg){: width=40 height=40}',
            '.svelte': '![Svelte](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/svelte/svelte-original.svg){: width=40 height=40}',
            '.html': '![HTML](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/html5/html5-original.svg){: width=40 height=40}',
            '.css': '![CSS](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/css3/css3-original.svg){: width=40 height=40}',
            '.md': '📝',
            '.json': '📊',
            '.xml': '📑',
            '.yml': '⚙️',
            '.yaml': '⚙️',
            '.sh': '💻',
            '.bat': '🪟',
            '.cpp': '![C++](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/cplusplus/cplusplus-original.svg){: width=40 height=40}',
            '.java': '![Java](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/java/java-original.svg){: width=40 height=40}',
            '.rb': '![Ruby](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/ruby/ruby-original.svg){: width=40 height=40}',
            '.go': '![Go](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/go/go-original.svg){: width=40 height=40}',
            '.rs': '![Rust](https://cdn.jsdelivr.net/gh/devicons/devicon/icons/rust/rust-original.svg){: width=40 height=40}'
        }
        return emoji_map.get(ext, '📄')

    def clean_summary(self, summary: str) -> str:
        """Clean up and ensure the summary adheres to the 1-3 sentence requirement."""
        summary = summary.strip()
        summary = summary.replace("**", "").replace("##", "").replace("#", "").strip()
        sentences = summary.split('.')
        clean_sentences = [s.strip() for s in sentences if s.strip()]
        return '. '.join(clean_sentences[:3]) + ('.' if clean_sentences else '')

    def analyze_file(self, filepath: str, model: str) -> str:
        """Analyze a file using the specified LLM model via llm_interface."""
        try:
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    content = file.read(2000)
            except UnicodeDecodeError:
                with open(filepath, 'r', encoding='latin-1') as file:
                    content = file.read(2000)

            filename = os.path.basename(filepath)
            prompt = (
                f"Describe this file's functionality in exactly 2 sentences. "
                f"Begin your response with 'This file' or 'This script' and explain what it does - nothing else.\n\n"
                f"Filename: {filename}\n\n"
                f"Content:\n{content}"
            )

            summary = llm_interface(prompt, model, 0.7, 0.9, 512)
            return self.clean_summary(summary) if summary else "Summary unavailable"
        except Exception as e:
            print(f"Error analyzing {filepath}: {e}")
            return "Unable to analyze file"
