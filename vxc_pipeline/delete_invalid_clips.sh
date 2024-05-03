#!/bin/bash

# This is a script that deletes all clips folder if there is a validated folder in all subfolders in a directory
# Created by Miao Zhang, 02.05.2024

# Get the path of the target directory from the script input
target_directory="$1"

# Check if target_directory is provided
if [[ -z "$target_directory" ]]; then
  echo "Usage: $0 <target_directory>"
  exit 1
fi

# Find all 'clips' folders and corresponding 'validated' folders in subdirectories of the target directory
find "$target_directory" -type d -name 'clips' | while read clips_dir; do
  # Check if the 'validated' folder exists in the same directory as 'clips'
  parent_dir=$(dirname "$clips_dir")
  validated_dir="${parent_dir}/validated"
  
  if [[ -d "$validated_dir" ]]; then
    echo "Deleting clips folder in: $clips_dir"
    rm -rf "$clips_dir"
  else
    echo "No 'validated' folder found for clips folder in: $parent_dir"
  fi
done

echo "Operation completed."