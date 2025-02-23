# camel_case_finder.py
import os
import re
from datetime import datetime
import sys
from llm_backend import llm_interface


class CamelCaseFinder:
    def __init__(self):
        # Store unique results as {original: (suggested, file_ext)}
        self.results = {}
        # Cache LLM outcomes as {(original, file_ext): is_library_related}
        self.llm_cache = {}
        # Define patterns for known file types
        self.patterns = {
            '.py': [
                (r'\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', 'class'),
                (r'\b(?:def|var|let|const)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', 'function_or_var')
            ],
            '.js': [
                (r'\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', 'class'),
                (r'\b(?:function|var|let|const)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', 'function_or_var')
            ],
            '.ts': [
                (r'\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', 'class'),
                (r'\b(?:function|var|let|const)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', 'function_or_var')
            ],
            '.svelte': [
                (r'\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', 'class'),
                (r'\b(?:function|var|let|const)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', 'function_or_var')
            ],
            '.html': [
                (r'\b(?:id|class)=["\']([a-zA-Z_][a-zA-Z0-9_]*?)["\']', 'attribute')
            ],
            '.css': [
                (r'(?<=[\{\s])[a-zA-Z_][a-zA-Z0-9_]*(?=\s*[:\{])', 'selector')
            ]
        }

    def is_snake_case(self, name):
        """Check if a name is already in snake_case."""
        return name == name.lower() and "_" in name or not any(c.isupper() for c in name)

    def is_camel_or_pascal(self, name):
        """Check if a name is in camelCase or PascalCase (allowed for classes)."""
        return (name[0].isupper() or (name[0].islower() and any(c.isupper() for c in name))) and "_" not in name

    def to_snake_case(self, name):
        """Convert a name to snake_case."""
        if not name:
            return name
        s = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        s = re.sub(r'_+', '_', s)
        return s.strip('_')

    def extract_imports(self, file_path):
        """Extract potential import statements from a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return set()

        ext = os.path.splitext(file_path)[1].lower()
        imports = set()

        if ext == '.py':
            import_pattern = r'^\s*import\s+([\w\.]+)(?:\s+as\s+\w+)?'
            from_import_pattern = r'^\s*from\s+([\w\.]+)\s+import\s+([\w,\s*]+)'
            for line in content.splitlines():
                import_match = re.match(import_pattern, line)
                if import_match:
                    imports.add(import_match.group(1))
                from_match = re.match(from_import_pattern, line)
                if from_match:
                    module = from_match.group(1)
                    imported_items = from_match.group(2).replace(' ', '').split(',')
                    imports.add(module)
                    imports.update(item for item in imported_items if item != '*')
        elif ext in ('.js', '.ts', '.svelte'):
            import_pattern = r'^\s*import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]'
            for line in content.splitlines():
                match = re.match(import_pattern, line)
                if match:
                    imports.add(match.group(1))

        return imports

    def is_library_related(self, name, imports, file_ext, model):
        """Ask LLM if the name is related to the imported packages using the provided model."""
        if not imports:
            return False

        language = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.svelte': 'Svelte/JavaScript',
        }.get(file_ext, 'Unknown')

        prompt = (
            f"Given the identifier '{name}' and the following imported {language} packages/modules: "
            f"{', '.join(imports)}, is '{name}' a class, function, or variable defined by any of these "
            f"packages or the {language} standard library? Answer 'Yes' or 'No'."
        )
        response = llm_interface(prompt, model, 0.7, 0.9, 512)
        return response.strip().lower() == 'yes'

    def get_patterns_for_ext(self, ext):
        """Get or prompt for regex patterns for a file extension."""
        if ext in self.patterns:
            return self.patterns[ext]

        print(f"Unknown file extension: {ext}. Please provide regex patterns.")
        patterns = []
        while True:
            pattern = input("Enter regex pattern (or 'done' to finish): ")
            if pattern.lower() == 'done':
                break
            decl_type = input("Enter declaration type (e.g., class, function_or_var): ")
            patterns.append((pattern, decl_type))
        self.patterns[ext] = patterns
        return patterns

    def find_non_snake_case(self, file_path, model):
        """Find variables/functions not in snake_case, excluding library-related names."""
        ext = os.path.splitext(file_path)[1].lower()
        file_patterns = self.get_patterns_for_ext(ext)
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
                for match in re.finditer(pattern, line):
                    name = match.group(1)
                    if decl_type == 'class' and self.is_camel_or_pascal(name):
                        continue
                    if not self.is_snake_case(name):
                        suggested = self.to_snake_case(name)
                        if suggested != name:
                            non_snake_cases.append((name, suggested, i, ext))

        # Filter out library-related names
        filtered_cases = []
        imports = self.extract_imports(file_path)
        if ext == '.py':
            imports.update(getattr(sys, 'stdlib_module_names', set()))

        for original, suggested, line_num, ext in non_snake_cases:
            cache_key = (original, ext)
            if cache_key in self.llm_cache:
                if not self.llm_cache[cache_key]:  # Not library-related
                    filtered_cases.append((original, suggested, line_num, ext))
            else:
                is_related = self.is_library_related(original, imports, ext, model)
                self.llm_cache[cache_key] = is_related
                if not is_related:  # Can be snake_case
                    filtered_cases.append((original, suggested, line_num, ext))

        return filtered_cases

    def scan_directory(self, repo_path: str, extensions: list, model: str):
        """Scan the repository for non-snake_case identifiers, excluding library names."""
        if not repo_path or not os.path.isdir(repo_path):
            return "Please enter a valid repository folder path"

        extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
        output = ["Scanning for non-snake_case identifiers (classes and library names excluded)..."]
        self.results = {}

        for root, _, files in os.walk(repo_path):
            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in extensions:
                    file_path = os.path.join(root, file)
                    non_snake_cases = self.find_non_snake_case(file_path, model)
                    if non_snake_cases:
                        relative_path = os.path.relpath(file_path, repo_path)
                        for original, suggested, line_num, ext in non_snake_cases:
                            if original not in self.results:
                                self.results[original] = (suggested, ext)
                            cache_key = (original, ext)
                            is_pkg = self.llm_cache.get(cache_key, "Pending")
                            output.append(f"{relative_path}: Line {line_num} - {original} -> {suggested} (Package: {is_pkg})")

        if not self.results:
            output.append("No non-snake_case identifiers found.")
        else:
            output.append(f"\nFound {len(self.results)} unique non-snake_case identifiers across files.")

        return "\n".join(output)

    def export_results(self, repo_path: str):
        """Export unique results with file type to a file in the repository path."""
        if not self.results:
            return "No results to export"

        if not repo_path or not os.path.isdir(repo_path):
            return "Invalid repository path for export"

        repo_name = repo_path.split('/app/shared_files/')[-1].replace('/', '_') or 'repo'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(repo_path, f"{repo_name}_non_snake_case_{timestamp}.txt")

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("File Type,Original Name,Suggested Snake Case,Package Related\n")
                for original, (suggested, file_ext) in self.results.items():
                    is_pkg = self.llm_cache.get((original, file_ext), "Unknown")
                    f.write(f"{file_ext},{original},{suggested},{is_pkg}\n")
            return f"Results exported to {output_file}"
        except Exception as e:
            return f"Error exporting results: {str(e)}"

    def load_results(self, export_file: str):
        """Load results from a previously exported file."""
        if not os.path.isfile(export_file):
            return f"Error: '{export_file}' is not a valid file."

        self.results = {}
        self.llm_cache = {}
        try:
            with open(export_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if not lines or lines[0].strip() != "File Type,Original Name,Suggested Snake Case,Package Related":
                    return "Error: Invalid file format."
                for line in lines[1:]:
                    parts = line.strip().split(',')
                    if len(parts) != 4:
                        continue
                    file_ext, original, suggested, is_pkg = parts
                    self.results[original] = (suggested, file_ext)
                    # Convert string 'True'/'False'/'Unknown' to boolean or leave as string
                    if is_pkg == 'True':
                        self.llm_cache[(original, file_ext)] = True
                    elif is_pkg == 'False':
                        self.llm_cache[(original, file_ext)] = False
                    else:
                        self.llm_cache[(original, file_ext)] = False  # Treat 'Unknown' as False for replacement
            return f"Loaded results from {export_file}. {len(self.results)} identifiers ready for replacement."
        except Exception as e:
            return f"Error loading results: {str(e)}"

    def replace_with_snake_case(self, repo_path: str, extensions: list = None):
        """Replace non-snake_case identifiers with their snake_case versions across all files."""
        if not self.results:
            return "No identifiers to replace. Please scan or load results first."

        if not repo_path or not os.path.isdir(repo_path):
            return "Invalid repository path"

        # If extensions are provided, filter results to only those matching the extensions
        if extensions:
            extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
            filtered_results = {
                original: (suggested, ext)
                for original, (suggested, ext) in self.results.items()
                if ext in extensions
            }
        else:
            filtered_results = self.results

        if not filtered_results:
            return "No identifiers match the specified file extensions."

        output = ["Replacing non-snake_case identifiers..."]
        updated_files = set()

        for root, _, files in os.walk(repo_path):
            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if extensions and file_ext not in extensions:
                    continue  # Skip files not matching the specified extensions
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    new_content = content
                    for original, (suggested, ext) in filtered_results.items():
                        if ext == file_ext:  # Only replace if file extension matches
                            pattern = rf'(?<!\w){re.escape(original)}(?!\w)'
                            new_content = re.sub(pattern, suggested, new_content)

                    if new_content != content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        relative_path = os.path.relpath(file_path, repo_path)
                        updated_files.add(relative_path)
                except Exception as e:
                    output.append(f"Error updating {file_path}: {str(e)}")

        if updated_files:
            output.extend([f"Updated {path}" for path in updated_files])
        output.append("Replacement complete.")
        self.results = {}  # Clear results after replacement
        self.llm_cache = {}  # Clear cache as well
        return "\n".join(output)
