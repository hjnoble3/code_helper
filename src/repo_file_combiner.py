# repo_file_combiner.py
import os


class RepoFileCombiner:
    def __init__(self):
        self.default_exclusions = ['node_modules', '.git', '.svn', '.hg']
        self.current_repo_path = None

        # List of binary and non-text file extensions to skip
        self.skip_extensions = [
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.svg',
            '.heic', '.raw', '.ico', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv',
            '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.zip', '.rar', '.7z',
            '.tar', '.gz', '.bz2', '.exe', '.dll', '.so', '.dylib', '.bin', '.pdf',
            '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.ttf', '.otf', '.woff',
            '.woff2', '.db', '.sqlite', '.mdb', '.pyc', '.class', '.o', '.obj'
        ]

    def select_repository(self, repo_path):
        """Set the repository path."""
        self.current_repo_path = repo_path
        return f"Selected repository: {repo_path}"

    def is_approved_file(self, file_path, approved_extensions):
        """Check if the file has an approved extension or should be included."""
        file_ext = os.path.splitext(file_path)[1].lower()
        # If approved_extensions is empty, include all files except those in skip_extensions
        if not approved_extensions:
            return file_ext not in self.skip_extensions
        # Otherwise, only include files with approved extensions
        return file_ext in [ext if ext.startswith('.') else f'.{ext}' for ext in approved_extensions]

    def combine_files(self, approved_extensions=None):
        """Combine files from the repository into a single file based on approved extensions."""
        if not self.current_repo_path:
            return "Please select a repository first"

        if not os.path.isdir(self.current_repo_path):
            self.current_repo_path = os.path.dirname(self.current_repo_path)
            if not os.path.isdir(self.current_repo_path):
                return f"Invalid repository path: {self.current_repo_path}"

        # Default to empty list if None is passed
        approved_extensions = approved_extensions or []
        output_file = os.path.join(self.current_repo_path, "combined_code.txt")
        all_exclusions = set(self.default_exclusions)

        try:
            with open(output_file, 'w', encoding='utf-8') as outfile:
                for root_dir, dirs, files in os.walk(self.current_repo_path):
                    dirs[:] = [d for d in dirs if d not in all_exclusions]
                    for file in files:
                        if any(exclusion in file for exclusion in all_exclusions):
                            continue
                        full_path = os.path.join(root_dir, file)
                        if not self.is_approved_file(full_path, approved_extensions):
                            continue
                        relative_path = os.path.relpath(full_path, self.current_repo_path)
                        try:
                            with open(full_path, 'r', encoding='utf-8') as infile:
                                outfile.write(f"FILE PATH: {relative_path}\n")
                                outfile.write("=" * 50 + "\n")
                                outfile.write(infile.read())
                                outfile.write("\n\n" + "="*80 + "\n\n")
                        except (UnicodeDecodeError, PermissionError, IOError) as e:
                            outfile.write(f"Skipped {relative_path} due to error: {str(e)}\n")
            return f"Files combined successfully. Output saved to {output_file}"
        except Exception as e:
            return f"An error occurred: {str(e)}"
