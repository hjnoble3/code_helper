import os

EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx', '.svelte']

SKIP_DIRS = ['node_modules', '.git', 'dist', 'build']


def find_files(directory):
    '''Find files with specified extensions in directory and subdirectories.'''
    files = []

    # Skip unnecessary directories to improve performance
    for root, dirs, filenames in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for filename in filenames:
            if any(filename.endswith(ext) for ext in EXTENSIONS):
                files.append(os.path.join(root, filename))

    return files


def save_file_over_itself(file_path):
    '''Save file over itself to trigger VSCode's auto-update functionality.'''
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)

        print(f"Processed: {file_path}")
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")


def process_repo():
    '''Process all files in the repository where this script is located.'''
    # Determine script's location for relative file processing
    script_dir = os.path.dirname(os.path.abspath(__file__))

    try:
        print(f"Finding files in {script_dir}...")

        files = find_files(script_dir)
        print(f"Found {len(files)} files to process.")

        for file in files:
            save_file_over_itself(file)

        print("Done! All files have been processed.")
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    process_repo()