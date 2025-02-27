# %%
import glob
import subprocess
import os
import re

# Function to get all .ts, .svelte, and .py files, excluding 'code_helper' folder


def get_files_excluding_code_helper(directory):
    ts_files = glob.glob(os.path.join(directory, '**', '*.ts'), recursive=True)
    svelte_files = glob.glob(os.path.join(directory, '**', '*.svelte'), recursive=True)
    py_files = glob.glob(os.path.join(directory, '**', '*.py'), recursive=True)
    all_files = ts_files + svelte_files + py_files
    all_files = [file for file in all_files if 'code_helper' not in file]  # Exclude 'code_helper' folder
    return all_files


# Function to remove comments from a file
def remove_comments(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    cleaned_lines = []
    for line in lines:
        if file_path.endswith('.ts'):
            # Treat `//` followed by a space as a valid comment and remove it.
            # We only remove lines that start with `//` followed by a space.
            line = re.sub(r'//\s.*', '', line)  # Remove comments starting with `//` followed by space

            # Remove TypeScript block comments (non-greedy match for block comments)
            line = re.sub(r'/\*.*?\*/', '', line)
        elif file_path.endswith('.svelte'):
            # Treat `<!--` as an HTML-style comment and remove it.
            line = re.sub(r'<!--.*?-->', '', line)  # Non-greedy match for Svelte HTML comments

            # Treat `//` followed by a space as a valid comment in <script> tags and remove it.
            line = re.sub(r'//\s.*', '', line)  # Remove comments starting with `//` followed by space
            # Remove block comments in <script> or <style> tags
            line = re.sub(r'/\*.*?\*/', '', line)

        cleaned_lines.append(line)

    with open(file_path, 'w', encoding='utf-8') as file:
        file.writelines(cleaned_lines)


# Function to run autoflake on Python files to remove unused imports and variables
def run_autoflake_on_files(py_files):
    for file in py_files:
        print(f"Processing with autoflake: {file}")
        subprocess.run(['autoflake', '--in-place', '--remove-all-unused-imports', '--remove-unused-variables', file])

    # Now, ensure comments are properly formatted with space after #
    for file in py_files:
        with open(file, 'r', encoding='utf-8') as file_obj:
            lines = file_obj.readlines()

        cleaned_lines = []
        for line in lines:
            # Replace multiple # with a single # followed by a space
            cleaned_line = re.sub(r'#+', '#', line)
            cleaned_line = re.sub(r'#(\S)', r'# \1', cleaned_line)  # Ensure single # has a space after it
            cleaned_lines.append(cleaned_line)

        with open(file, 'w', encoding='utf-8') as file_obj:
            file_obj.writelines(cleaned_lines)


# Function to process the directory
def process_directory(directory):
    # Get .ts, .svelte, and .py files excluding the 'code_helper' folder
    files = get_files_excluding_code_helper(directory)
    py_files = [file for file in files if file.endswith('.py')]
    ts_svelte_files = [file for file in files if file.endswith(('.ts', '.svelte'))]

    # Process comments in TypeScript and Svelte files
    for file in ts_svelte_files:
        print(f"Processing comments in: {file}")
        remove_comments(file)

    # Run autoflake on Python files
    if py_files:
        run_autoflake_on_files(py_files)

    print(f"Processed {len(ts_svelte_files)} TypeScript and Svelte files.")
    print(f"Processed {len(py_files)} Python files.")


# Main function
if __name__ == "__main__":
    project_dir = input("Enter the root directory of your project: ")
    process_directory(project_dir)

# %%
