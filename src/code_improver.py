# code_improver.py
import os
import re
from typing import Dict, Set, Tuple, Optional, Union
from tqdm import tqdm


class CodeImprover:
    """A tool to enhance code quality through improved documentation, formatting, and optimization."""

    SUPPORTED_EXTENSIONS = {'.py', '.js', '.ts', '.svelte', '.html', '.css'}
    COMMENT_INDICATORS = {
        '.py': ('#', ''),
        '.js': ('//', ''),
        '.ts': ('//', ''),
        '.svelte': None,  # Handled dynamically
        '.html': ('<!--', '-->'),
        '.css': ('/*', '*/')
    }

    def __init__(self, style_guide: str = 'default'):
        """Initialize CodeImprover with style guide specifications."""
        self.style_guide = style_guide.lower()

    def _get_comment_style(self, ext: str, content: str = None) -> Tuple[str, str]:
        """Get appropriate comment markers for a file extension and content context."""
        if ext != '.svelte':
            return self.COMMENT_INDICATORS.get(ext, ('#', '') if ext == '.py' else ('//', ''))

        if not content:
            return ('<!--', '-->')

        if '<script' in content and '</script>' in content:
            return ('//', '')
        elif '<style' in content and '</style>' in content:
            return ('/*', '*/')
        return ('<!--', '-->')

    def _get_style_guide_prompt(self, ext: str) -> str:
        """Determine appropriate style guide based on file type."""
        style_mapping = {
            '.py': 'Google Python Style Guide' if self.style_guide == 'google' else 'PEP 8',
            '.js': 'Airbnb JavaScript Style Guide' if self.style_guide == 'airbnb' else 'Microsoft TypeScript guidelines',
            '.ts': 'Airbnb JavaScript Style Guide' if self.style_guide == 'airbnb' else 'Microsoft TypeScript guidelines',
            '.svelte': 'Svelte style guide',
            '.html': 'W3C HTML guidelines with consistent indentation and tag nesting',
            '.css': 'CSS guidelines with consistent spacing and property ordering'
        }
        return style_mapping.get(ext, 'language-specific best practices')


    def get_prompt(self, file_path: str, options: Dict[str, bool]) -> Optional[str]:
        """Generate a tailored improvement prompt based on selected options and file type."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            original_code = f.read()

        comment_start, comment_end = self._get_comment_style(ext, original_code)
        style_guide = self._get_style_guide_prompt(ext)
        lang = ext[1:].upper()

        prompt = (
            f"Enhance the following {lang} code:\n\n"
            f"```plaintext\n{original_code}\n```\n\n"
            "Apply these improvements:\n"
        )

        if options.get('Add Docstrings'):
            prompt += (
                f"- Replace all existing comments (starting with {comment_start}) with detailed docstrings for functions and classes. "
                f"Include purpose, parameters, return values, and side effects. Use {comment_start}{' ' + comment_end if comment_end else ''} "
                f"for inline comments where needed. Adhere to PEP 257 for Python, JSDoc for TypeScript/JavaScript, and add HTML comments in Svelte.\n"
            )

        if options.get('Improve Formatting'):
            prompt += (
                f"- Reformat code per {style_guide}, adjusting indentation, spacing, line length, and import ordering.\n"
            )

        if options.get('Optimize Code'):
            prompt += "- Optimize for performance, preserving readability.\n"

        if options.get('Enhance Error Handling'):
            prompt += "- Implement robust error handling with clear, actionable error messages.\n"

        if options.get('Verify Documentation'):
            prompt += "- Ensure all functions and classes have complete, accurate documentation.\n"

        if options.get('Remove i18n'):
            prompt += "- Replace i18n code with plain English text.\n"

        if options.get('Restrict AI Providers'):
            prompt += "- Remove references to AI providers other than Hugging Face or Ollama.\n"

        if options.get('Cleanup Dependencies'):
            prompt += "- Eliminate unused imports and dead code.\n"

        if any(options.values()):
            prompt += "\nOutput only the improved code within ```plaintext``` tags."
            return prompt
        return None

    def improve_file(self, file_path: str, options: Dict[str, bool], model: str) -> str:
        """Improve a single code file using LLM processing."""
        from llm_backend import llm_interface  # Assuming this exists

        prompt = self.get_prompt(file_path, options)
        if not prompt:
            return f"Error: Unsupported file type or no improvements selected for {file_path}"

        response = llm_interface(
            prompt=prompt,
            model=model,
            temperature=0.25,  # Very literal, deterministic output
            top_p=.9,
            max_tokens=1024
        )

        if response.startswith("Error"):
            return f"Error improving {file_path}: {response}"

        code_match = re.search(r'```plaintext\n([\s\S]*?)\n```', response)
        if not code_match:
            return f"Error: No valid code returned for {file_path}"

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(code_match.group(1))
        return f"Improved {file_path}"

    def improve_directory(self, repo_path: str, extensions: Set[str], options: Dict[str, bool], model: str) -> str:
        """Process all matching files in a directory with progress tracking."""
        if not os.path.isdir(repo_path):
            return "Invalid repository path"

        extensions = {f".{ext}" if not ext.startswith('.') else ext for ext in extensions}
        unsupported = extensions - self.SUPPORTED_EXTENSIONS
        if unsupported:
            extensions -= unsupported
            print(f"Warning: Ignoring unsupported extensions: {unsupported}")

        output = ["Improving scripts..."]
        files_to_process = [
            os.path.join(root, file)
            for root, _, files in os.walk(repo_path)
            for file in files
            if os.path.splitext(file)[1].lower() in extensions
        ]

        for file_path in tqdm(files_to_process, desc="Processing files", unit="file"):
            output.append(self.improve_file(file_path, options, model))

        output.append("Improvement complete.")
        return "\n".join(output)
