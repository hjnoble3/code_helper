import os
import re
import json
from datetime import datetime
import sys
from pathlib import Path
from multiprocessing import Pool, cpu_count
from llm_backend import llm_interface


class CamelCaseFinder:
    def __init__(self):
        self.results = {}  # {original: (suggested, file_ext)}
        self.llm_cache = {}  # {(original, file_ext): is_library_related}
        self.patterns = {
            '.py': [
                (re.compile(r'\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'), 'class'),
                (re.compile(r'\b(?:def|var|let|const)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'), 'function_or_var')
            ],
            '.js': [
                (re.compile(r'\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'), 'class'),
                (re.compile(r'\b(?:function|var|let|const)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'), 'function_or_var')
            ],
            '.ts': [
                (re.compile(r'\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'), 'class'),
                (re.compile(r'\b(?:function|var|let|const)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'), 'function_or_var')
            ],
            '.svelte': [
                (re.compile(r'\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'), 'class'),
                (re.compile(r'\b(?:function|var|let|const)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'), 'function_or_var')
            ],
            '.html': [
                (re.compile(r'\b(?:id|class)=["\']([a-zA-Z_][a-zA-Z0-9_]*?)["\']'), 'attribute')
            ],
            '.css': [
                (re.compile(r'(?<=[\{\s])[a-zA-Z_][a-zA-Z0-9_]*(?=\s*[:\{])'), 'selector')
            ]
        }
        self.camel_to_snake = re.compile(r'(?<!^)(?=[A-Z])')
        self.multi_underscore = re.compile(r'_+')

    def is_snake_case(self, name):
        return "_" in name or not any(c.isupper() for c in name)

    def is_camel_or_pascal(self, name):
        return (name[0].isupper() or (name[0].islower() and any(c.isupper() for c in name))) and "_" not in name

    def to_snake_case(self, name):
        if not name:
            return name
        s = self.camel_to_snake.sub('_', name).lower()
        s = self.multi_underscore.sub('_', s)
        return s.strip('_')

    def extract_imports(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return set()

        ext = os.path.splitext(file_path)[1].lower()
        imports = set()

        if ext == '.py':
            import_pattern = re.compile(r'^\s*import\s+([\w\.]+)(?:\s+as\s+\w+)?', re.MULTILINE)
            from_import_pattern = re.compile(r'^\s*from\s+([\w\.]+)\s+import\s+([\w,\s*]+)', re.MULTILINE)
            for match in import_pattern.finditer(content):
                imports.add(match.group(1))
            for match in from_import_pattern.finditer(content):
                module = match.group(1)
                imported_items = match.group(2).replace(' ', '').split(',')
                imports.add(module)
                imports.update(item for item in imported_items if item != '*')
        elif ext in ('.js', '.ts', '.svelte'):
            import_pattern = re.compile(r'^\s*import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]', re.MULTILINE)
            for match in import_pattern.finditer(content):
                imports.add(match.group(1))

        return imports

    def batch_is_library_related(self, identifiers, imports, file_ext, model):
        if not imports or not identifiers:
            return {ident: False for ident in identifiers}

        language = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.svelte': 'Svelte/JavaScript',
        }.get(file_ext, 'Unknown')

        prompt = (
            f"For each identifier below, determine if it is a class, function, or variable defined by the "
            f"following imported {language} packages/modules: {', '.join(imports)} or the {language} standard library.\n"
            f"Provide answers as a JSON object where keys are identifiers and values are 'Yes' or 'No'.\n\n"
            f"Identifiers: {', '.join(identifiers)}"
        )
        response = llm_interface(prompt, model, 0.7, 0.9, 512)
        try:
            results = json.loads(response)
            return {ident: results.get(ident, 'No').lower() == 'yes' for ident in identifiers}
        except Exception:
            return {ident: False for ident in identifiers}

    def find_non_snake_case(self, args):
        file_path, model = args
        ext = os.path.splitext(file_path)[1].lower()
        file_patterns = self.patterns.get(ext, [])
        if not file_patterns:
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return []

        non_snake_cases = []
        for i, line in enumerate(lines, 1):
            for pattern, decl_type in file_patterns:
                for match in pattern.finditer(line):
                    name = match.group(1)
                    if decl_type == 'class' and self.is_camel_or_pascal(name):
                        continue
                    if not self.is_snake_case(name):
                        suggested = self.to_snake_case(name)
                        if suggested != name:
                            non_snake_cases.append((name, suggested, i, ext))

        return non_snake_cases

    def scan_directory(self, repo_path: str, extensions: list, model: str, progress=None):
        """Scan the repository with Gradio progress updates."""
        repo = Path(repo_path)
        if not repo.is_dir():
            return "Please enter a valid repository folder path"

        extensions = {ext if ext.startswith('.') else f'.{ext}' for ext in extensions}
        output = ["Scanning for non-snake_case identifiers (classes and library names excluded)..."]
        self.results = {}

        files_to_process = [f for f in repo.rglob('*') if f.is_file() and f.suffix.lower() in extensions]
        if not files_to_process:
            output.append("No matching files found.")
            return "\n".join(output)

        total_files = len(files_to_process)
        # Initialize progress with the total number of files
        if progress is not None:
            progress((0, total_files), desc="Starting scan...", total=total_files)

        with Pool(cpu_count()) as pool:
            file_results = pool.imap_unordered(self.find_non_snake_case, [(str(f), model) for f in files_to_process])

            all_non_snake = {}
            imports_cache = {}
            processed_files = 0

            for file_result, file_path in zip(file_results, files_to_process):
                processed_files += 1
                if progress is not None:
                    progress((processed_files, total_files), desc=f"Scanned {processed_files}/{total_files} files", total=total_files)

                if not file_result:
                    continue
                relative_path = str(file_path.relative_to(repo))
                ext = file_path.suffix.lower()
                imports = imports_cache.setdefault(file_path, self.extract_imports(file_path))
                if ext == '.py':
                    imports.update(getattr(sys, 'stdlib_module_names', set()))

                for original, suggested, line_num in file_result:
                    if original not in self.results:
                        self.results[original] = (suggested, ext)
                    all_non_snake.setdefault(file_path, []).append((original, suggested, line_num))

        for file_path, cases in all_non_snake.items():
            ext = file_path.suffix.lower()
            identifiers = [original for original, _, _ in cases]
            imports = imports_cache[file_path]
            batch_results = self.batch_is_library_related(identifiers, imports, ext, model)
            for original, suggested, line_num in cases:
                cache_key = (original, ext)
                is_related = batch_results.get(original, False)
                self.llm_cache[cache_key] = is_related
                if not is_related:
                    output.append(f"{file_path.relative_to(repo)}: Line {line_num} - {original} -> {suggested} (Package: {is_related})")

        if not self.results:
            output.append("No non-snake_case identifiers found.")
        else:
            output.append(f"\nFound {len(self.results)} unique non-snake_case identifiers across files.")

        return "\n".join(output)

    def export_results(self, repo_path: str):
        if not self.results:
            return "No results to export"

        repo = Path(repo_path)
        if not repo.is_dir():
            return "Invalid repository path for export"

        repo_name = repo.name or 'repo'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = repo / f"{repo_name}_non_snake_case_{timestamp}.txt"

        try:
            with output_file.open('w', encoding='utf-8') as f:
                f.write("File Type,Original Name,Suggested Snake Case,Package Related\n")
                for original, (suggested, file_ext) in self.results.items():
                    is_pkg = self.llm_cache.get((original, file_ext), "Unknown")
                    f.write(f"{file_ext},{original},{suggested},{is_pkg}\n")
            return f"Results exported to {output_file}"
        except Exception as e:
            return f"Error exporting results: {str(e)}"

    def load_results(self, export_file: str):
        export_path = Path(export_file)
        if not export_path.is_file():
            return f"Error: '{export_file}' is not a valid file."

        self.results = {}
        self.llm_cache = {}
        try:
            with export_path.open('r', encoding='utf-8') as f:
                lines = f.readlines()
                if not lines or lines[0].strip() != "File Type,Original Name,Suggested Snake Case,Package Related":
                    return "Error: Invalid file format."
                for line in lines[1:]:
                    parts = line.strip().split(',')
                    if len(parts) != 4:
                        continue
                    file_ext, original, suggested, is_pkg = parts
                    self.results[original] = (suggested, file_ext)
                    self.llm_cache[(original, file_ext)] = is_pkg == 'True'
            return f"Loaded results from {export_file}. {len(self.results)} identifiers ready for replacement."
        except Exception as e:
            return f"Error loading results: {str(e)}"

    def replace_with_snake_case(self, repo_path: str, extensions: list = None):
        if not self.results:
            return "No identifiers to replace. Please scan or load results first."

        repo = Path(repo_path)
        if not repo.is_dir():
            return "Invalid repository path"

        extensions = {ext if ext.startswith('.') else f'.{ext}' for ext in (extensions or [])}
        filtered_results = self.results if not extensions else {
            orig: (sug, ext) for orig, (sug, ext) in self.results.items() if ext in extensions
        }

        if not filtered_results:
            return "No identifiers match the specified file extensions."

        output = ["Replacing non-snake_case identifiers..."]
        updated_files = set()

        for file_path in repo.rglob('*'):
            if not file_path.is_file() or (extensions and file_path.suffix.lower() not in extensions):
                continue
            ext = file_path.suffix.lower()
            try:
                with file_path.open('r', encoding='utf-8') as f:
                    content = f.read()

                new_content = content
                for original, (suggested, file_ext) in filtered_results.items():
                    if file_ext == ext:
                        pattern = rf'(?<!\w){re.escape(original)}(?!\w)'
                        new_content = re.sub(pattern, suggested, new_content)

                if new_content != content:
                    with file_path.open('w', encoding='utf-8') as f:
                        f.write(new_content)
                    updated_files.add(str(file_path.relative_to(repo)))
            except Exception as e:
                output.append(f"Error updating {file_path}: {str(e)}")

        if updated_files:
            output.extend([f"Updated {path}" for path in updated_files])
        output.append("Replacement complete.")
        self.results = {}
        self.llm_cache = {}
        return "\n".join(output)
