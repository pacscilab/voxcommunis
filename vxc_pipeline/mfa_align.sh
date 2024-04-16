#!/bin/bash

# Check if at least six arguments (directory path, three additional files, starting number, ending number) are provided
if [ $# -lt 5 ]; then
    echo "Usage: $0 <directory_path> <file1> <file2> <file3> <start_num> <how_many>"
    exit 1
fi

# Assign the arguments to variables
directory_path="$1"
file1="$2"
file2="$3"
file3="$4"
start_num="$5"
how_many="$6"

# Calculate the ending number

# Find all subfolders and skip the first (start_num - 1) lines, then limit the output
subfolders_range=$(find "$directory_path" -mindepth 1 -maxdepth 1 -type d | sort | tail -n +$((start_num)) | head -n $((how_many)))

# Loop through the subfolders in the specified range
for subfolder in $subfolders_range; do
    echo "Processing subfolder: $subfolder"
    # Execute the mfa align --clean command for each subfolder
    #mfa align --clean "$directory_path/$subfolder" "$file1" "$file2" "$file3"
done