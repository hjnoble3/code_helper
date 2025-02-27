# !/usr/bin/env python3
import os
import re
import argparse
import fnmatch


def replace_in_file_content(file_path, patterns, replacement):
    """Replace all occurrences of multiple patterns with replacement in the given file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()

        # Check if any pattern matches before modifying
        modified = False
        new_content = content

        for pattern in patterns:
            if re.search(pattern, new_content, re.IGNORECASE):
                new_content = re.sub(pattern, replacement, new_content, flags=re.IGNORECASE)
                modified = True

        if modified:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(new_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return False


def rename_file_or_dir(path, patterns, replacement):
    """Rename a file or directory if its name matches any of the patterns."""
    dirname, basename = os.path.split(path)
    new_basename = basename

    for pattern in patterns:
        if re.search(pattern, new_basename, re.IGNORECASE):
            new_basename = re.sub(pattern, replacement, new_basename, flags=re.IGNORECASE)

    if new_basename != basename:
        new_path = os.path.join(dirname, new_basename)
        try:
            os.rename(path, new_path)
            return new_path
        except Exception as e:
            print(f"Error renaming {path}: {e}")
    return path


def process_repository(repo_path, patterns, replacement, file_types, exclude_dirs):
    """Process all files and directories in the repository."""
    # Track statistics
    stats = {
        'files_processed': 0,
        'files_modified': 0,
        'files_renamed': 0,
        'dirs_renamed': 0
    }

    # Collect all files and directories to process
    all_files = []
    all_dirs = []

    for root, dirs, files in os.walk(repo_path, topdown=False):
        # Skip excluded directories
        skip_dir = False
        for exclude in exclude_dirs:
            if exclude in root.split(os.sep):
                skip_dir = True
                break
        if skip_dir:
            continue

        # Add directories to list
        for d in dirs:
            dir_path = os.path.join(root, d)
            all_dirs.append(dir_path)

        # Add files to list
        for f in files:
            file_path = os.path.join(root, f)
            # Check if file matches any of the patterns we're looking for
            if any(fnmatch.fnmatch(f, f'*{ft}') for ft in file_types):
                all_files.append(file_path)

    # Process file contents
    print("Modifying file contents...")
    for file_path in all_files:
        stats['files_processed'] += 1
        if replace_in_file_content(file_path, patterns, replacement):
            stats['files_modified'] += 1
            print(f"Modified content in: {file_path}")

    # Rename files (starting with deepest paths)
    print("\nRenaming files...")
    all_files.sort(key=lambda x: x.count(os.sep), reverse=True)
    renamed_files = {}

    for file_path in all_files:
        # Check if any parent directory was renamed
        new_path = file_path
        for old_dir, new_dir in renamed_files.items():
            if new_path.startswith(old_dir + os.sep):
                new_path = new_path.replace(old_dir, new_dir, 1)

        # Now try to rename the file itself
        new_file_path = rename_file_or_dir(new_path, patterns, replacement)
        if new_file_path != new_path:
            renamed_files[new_path] = new_file_path
            stats['files_renamed'] += 1
            print(f"Renamed file: {new_path} -> {new_file_path}")

    # Rename directories (starting with deepest paths)
    print("\nRenaming directories...")
    all_dirs.sort(key=lambda x: x.count(os.sep), reverse=True)
    renamed_dirs = {}

    for dir_path in all_dirs:
        # Check if any parent directory was renamed
        new_path = dir_path
        for old_dir, new_dir in renamed_dirs.items():
            if new_path.startswith(old_dir + os.sep):
                new_path = new_path.replace(old_dir, new_dir, 1)

        # Now try to rename the directory itself
        new_dir_path = rename_file_or_dir(new_path, patterns, replacement)
        if new_dir_path != new_path:
            renamed_dirs[new_path] = new_dir_path
            stats['dirs_renamed'] += 1
            print(f"Renamed directory: {new_path} -> {new_dir_path}")

    return stats


def main():
    parser = argparse.ArgumentParser(description='Replace text in repository files and rename matching files/directories')
    parser.add_argument('repo_path', help='Path to the repository')
    parser.add_argument('--replacement', default='temp_name', help='Text to replace with (default: temp_name)')
    parser.add_argument('--file-types', default='.py,.svelte,.ts,.js,.jsx,.tsx,.html,.css,.json,.md,.txt,.sh,.yml,.yaml',
                        help='Comma-separated list of file extensions to process')
    parser.add_argument('--exclude-dirs', default='.git,node_modules,venv,__pycache__',
                        help='Comma-separated list of directories to exclude')

    args = parser.parse_args()

    # Define patterns to catch all variations of "webui"
    patterns = [
        r'webui',                 # webui
        r'open[_\-\s]?webui',         # webui, webui, webui
        r'open[_\-\s]?web[_\-\s]?ui',  # webui, webui, etc.
    ]

    file_types = args.file_types.split(',')
    exclude_dirs = args.exclude_dirs.split(',')

    print(f"Starting repository processing at: {args.repo_path}")
    print(f"Replacing patterns: {patterns}")
    print(f"With: {args.replacement}")
    print(f"In file types: {file_types}")
    print(f"Excluding directories: {exclude_dirs}")

    stats = process_repository(args.repo_path, patterns, args.replacement, file_types, exclude_dirs)

    print("\nProcessing complete!")
    print(f"Files processed: {stats['files_processed']}")
    print(f"Files with modified content: {stats['files_modified']}")
    print(f"Files renamed: {stats['files_renamed']}")
    print(f"Directories renamed: {stats['dirs_renamed']}")


if __name__ == "__main__":
    main()

# Look for the pattern open[\s_]?webui (which matches webui, webui, webui, etc.)
# Replace all matches with "temp_name"
# python replace_script.py /path/to/repository --replacement "webui" --file-types ".py,.js,.svelte" --exclude-dirs ".git,build"
