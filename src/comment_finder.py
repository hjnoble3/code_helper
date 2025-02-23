# comment_finder.py
import os
import re
from datetime import datetime


class CommentFinder:
    def __init__(self):
        # Define comment patterns for supported extensions
        self.comment_patterns = {
            '.py': r'^\s*#',
            '.ts': r'^\s*//',
            '.js': r'^\s*//',
            '.svelte': r'^\s*//',
            '.html': r'^\s*<!--',
            '.css': r'^\s*/\*'
        }
        self.results = {}  # Store results for later use

    def find_consecutive_comments(self, file_path: str):
        """Find consecutive comment lines in a file based on its extension."""
        ext = os.path.splitext(file_path)[1].lower()
        comments = []

        # Skip if extension not supported
        if ext not in self.comment_patterns:
            return []

        comment_pattern = self.comment_patterns[ext]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return []

        consecutive_comments = []
        start_line = None

        for i, line in enumerate(lines, 1):
            if re.match(comment_pattern, line):
                if not start_line:
                    start_line = i
                consecutive_comments.append(line.strip())
            else:
                if len(consecutive_comments) > 1:  # Only include if more than one consecutive comment
                    comments.append((start_line, i - 1, consecutive_comments))
                consecutive_comments = []
                start_line = None

        if len(consecutive_comments) > 1:
            comments.append((start_line, len(lines), consecutive_comments))

        return comments

    def scan_directory(self, repo_path: str, extensions: list):
        """Scan the repository for files with consecutive comments."""
        if not repo_path or not os.path.isdir(repo_path):
            return "Please enter a valid repository folder path"

        # Normalize extensions
        extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
        output = ["Scanning for consecutive comments..."]
        self.results = {}

        for root, _, files in os.walk(repo_path):
            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in extensions:
                    file_path = os.path.join(root, file)
                    comments = self.find_consecutive_comments(file_path)
                    if comments:
                        self.results[file_path] = comments
                        relative_path = os.path.relpath(file_path, repo_path)
                        for start_line, end_line, _ in comments:
                            output.append(f"{relative_path}: Lines {start_line}-{end_line}")

        if not self.results:
            output.append("No consecutive comments found.")
        else:
            output.append(f"\nFound consecutive comments in {len(self.results)} file(s).")

        return "\n".join(output)

    def export_results(self, repo_path: str):
        """Export the results to a file in the repository path."""
        if not self.results:
            return "No results to export"

        if not repo_path or not os.path.isdir(repo_path):
            return "Invalid repository path for export"

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(repo_path, f"consecutive_comments_{timestamp}.txt")

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                for file_path, comments in self.results.items():
                    relative_path = os.path.relpath(file_path, repo_path)
                    f.write(f"\n{relative_path}:\n")
                    for start_line, end_line, content in comments:
                        f.write(f"  Lines {start_line}-{end_line}:\n")
                        for line in content:
                            f.write(f"    {line}\n")
            return f"Results exported to {output_file}"
        except Exception as e:
            return f"Error exporting results: {str(e)}"

    def delete_comments(self, repo_path: str):
        """Delete consecutive comments from files, processing from last to first."""
        if not self.results:
            return "No comments to delete. Please scan first."

        if not repo_path or not os.path.isdir(repo_path):
            return "Invalid repository path"

        output = ["Deleting consecutive comments..."]
        for file_path, comments in self.results.items():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # Sort comments by start_line in reverse order to avoid shifting
                comments_sorted = sorted(comments, key=lambda x: x[0], reverse=True)

                for start_line, end_line, _ in comments_sorted:
                    # Adjust for 0-based indexing
                    start_idx = start_line - 1
                    end_idx = end_line
                    del lines[start_idx:end_idx]

                # Write updated content back to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)

                relative_path = os.path.relpath(file_path, repo_path)
                output.append(f"Deleted comments from {relative_path}")
            except Exception as e:
                output.append(f"Error deleting comments in {file_path}: {str(e)}")

        # Clear results after deletion
        self.results = {}
        output.append("Deletion complete.")
        return "\n".join(output)
