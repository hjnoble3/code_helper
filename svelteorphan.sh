#!/bin/bash

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# get the list of all .svelte and .ts files
svelte_files=$(find src -type f -name "*.svelte")
ts_files=$(find src -type f -name "*.ts")

# Array to hold unused files
declare -a unused_files

echo -e "${NC}Scanning src folder to find all .svelte and .ts files"
echo -e "  ${GREEN}.${NC} means the file is imported in another file"
echo -e "  ${RED}x${NC} means the file is not imported and should likely be removed"

# Function to check if a file is used
check_file_usage() {
    local file_path="$1"
    local extension="$2"

    # extract the filename
    filename=$(basename -- "$file_path")
    # get filename without extension for .ts files
    filename_no_ext="${filename%.*}"

    # skip files starting with '+'
    if [[ "$filename" == +* ]]
    then
        echo -n -e "${GREEN}.${NC}"
        return 0
    fi

    # search for the filename in all files
    if [ "$extension" = "ts" ]; then
        # For TS files, check both with and without extension
        found=$(grep -rl -E "($filename|$filename_no_ext)" src)
    else
        found=$(grep -rl "$filename" src)
    fi

    # if nothing was found, then the file is unused
    if [[ -z $found ]]
    then
        echo -n -e "${RED}x${NC}"
        unused_files+=("$file_path")
    else
        echo -n -e "${GREEN}.${NC}"
    fi
}

# Process Svelte files
for svelte_file in $svelte_files
do
    check_file_usage "$svelte_file" "svelte"
done

# Process TS files
for ts_file in $ts_files
do
    check_file_usage "$ts_file" "ts"
done

# Print a newline after progress dots
echo
echo

# Print unused files
for file in "${unused_files[@]}"
do
    echo -e "${RED}Unused file: $file${NC}"
done

# If no unused components found, print the message and exit
if [ ${#unused_files[@]} -eq 0 ]; then
    echo -e "${GREEN}No unused components found.${NC}"
    exit 0
fi

# Delete files if user confirms
if [ ${#unused_files[@]} -gt 0 ]; then
    echo -e -n "${GREEN}Do you want to delete these ${#unused_files[@]} files? (y/n) ${NC}"
    read answer

    if [ "$answer" != "${answer#[Yy]}" ] ;then
        for file in "${unused_files[@]}"
        do
            rm "$file"
            echo -e "${RED}Deleted $file${NC}"
        done
    fi
fi