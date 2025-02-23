# src/file_checker.py
import os
import re
from pathlib import Path


def find_unused_files(folder_path, file_extensions):
    """Find unused files of specified extensions in the given folder."""
    print(f"Received folder_path: {folder_path}")
    print(f"Received file_extensions: {file_extensions}")

    folder = Path(folder_path)
    output = [f"Checking folder: {folder.resolve()}"]
    print(f"Resolved folder: {folder.resolve()}")

    if not folder.exists():
        return "Folder does not exist."
    if not folder.is_dir():
        return "Path is not a directory."

    # Ensure extensions are properly formatted
    extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in file_extensions.split(',')]
    output.append(f"Searching for extensions: {extensions}")
    print(f"Searching extensions: {extensions}")

    # Collect files for each extension individually
    files_to_check = []
    for ext in extensions:
        found_files = list(folder.rglob(f"*{ext}"))
        files_to_check.extend(found_files)
        print(f"Files found with '{ext}': {[str(f) for f in found_files]}")

    output.append(f"Files found: {len(files_to_check)}")
    if files_to_check:
        output.append("Detected files:")
        output.extend([f" - {f}" for f in files_to_check])
    else:
        output.append(f"No files with extensions {extensions} found.")

    if not files_to_check:
        return "\n".join(output)

    unused_files = []
    output.append("\nScanning for unused files...")

    for file in files_to_check:
        filename = file.name
        if filename.startswith('+'):
            output.append(f"✓ {filename} (skipped, starts with '+')")
            continue

        found = False
        for root, _, files in os.walk(folder):
            for other_file in files:
                if other_file == filename:
                    continue
                file_path = Path(root) / other_file
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        if re.search(re.escape(filename), f.read()):
                            found = True
                            break
                except Exception:
                    continue
            if found:
                break

        if not found:
            output.append(f"✗ {filename} (unused)")
            unused_files.append(str(file))
        else:
            output.append(f"✓ {filename} (used)")

    if not unused_files:
        output.append(f"\nNo unused files found for extensions {extensions}.")
    else:
        output.append(f"\nFound {len(unused_files)} unused file(s):")
        output.extend([f" - {f}" for f in unused_files])

    final_output = "\n".join(output)
    print("Final output:\n", final_output)
    return final_output


def delete_unused_files(folder_path, file_extensions, confirm=False):
    """Delete unused files of specified extensions if confirmed."""
    result = find_unused_files(folder_path, file_extensions)
    if "No unused files" in result or "No files with extensions" in result:
        return result

    unused_files = [line.split(" - ")[1] for line in result.splitlines() if line.startswith(" - ")]
    if not confirm:
        return result + "\n\nSet confirm=True to delete these files."

    for file in unused_files:
        try:
            os.remove(file)
            result += f"\nDeleted: {file}"
        except Exception as e:
            result += f"\nError deleting {file}: {e}"
    return result
