#!/bin/bash

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Get the list of all .py files in the entire directory, excluding __pycache__
py_files=$(find . -type f -name "*.py" -not -path "*/__pycache__/*")

# Array to hold unused files
declare -a unused_files

echo -e "${NC}Scanning entire directory for .py files (excluding __pycache__)"
echo -e "  ${GREEN}.${NC} means the file is imported or contains API endpoints"
echo -e "  ${RED}x${NC} means the file appears unused and could be removed"

# Function to check if a file is used
check_file_usage() {
    local file_path="$1"

    # Extract the filename
    filename=$(basename -- "$file_path")
    filename_no_ext="${filename%.*}"

    # Skip common Python entry points, configs, and special files
    if [[ "$filename" =~ ^(main|app|server|config|setup|__init__)\.py$ ]]; then
        echo -n -e "${GREEN}.${NC}"
        return 0
    fi

    # Check if file contains API endpoint patterns (Flask/FastAPI style)
    if grep -E "(@app\.route|@app\.(get|post|put|delete)|@router\.(get|post|put|delete))" "$file_path" > /dev/null 2>&1; then
        echo -n -e "${GREEN}.${NC}"
        return 0
    fi

    # Search for the filename in all Python files
    found=$(grep -rl "$filename_no_ext" . --include="*.py" --exclude-dir=__pycache__)

    # If nothing was found, then the file is unused
    if [[ -z $found ]]; then
        echo -n -e "${RED}x${NC}"
        unused_files+=("$file_path")
    else
        echo -n -e "${GREEN}.${NC}"
    fi
}

# Process Python files
for py_file in $py_files; do
    check_file_usage "$py_file"
done

# Print a newline after progress dots
echo
echo

# Print unused files
for file in "${unused_files[@]}"; do
    echo -e "${RED}Unused file: $file${NC}"
done

# If no unused files found, print the message and exit
if [ ${#unused_files[@]} -eq 0 ]; then
    echo -e "${GREEN}No unused files found.${NC}"
    exit 0
fi

# Delete files if user confirms
if [ ${#unused_files[@]} -gt 0 ]; then
    echo -e -n "${GREEN}Do you want to delete these ${#unused_files[@]} files? (y/n) ${NC}"
    read answer

    if [ "$answer" != "${answer#[Yy]}" ]; then
        for file in "${unused_files[@]}"; do
            rm "$file"
            echo -e "${RED}Deleted $file${NC}"
        done
    fi
fi