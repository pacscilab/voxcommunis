#!/bin/bash

# Created by Miao Zhang, 04/19/2024

start=$(date +%s)

# Check if arguments are provided
if [ $# -lt 4 ]; then
    echo "Usage: $0 <validated_recs_path> <dict_file_path> <acs_mod_path> <output_path>"
    exit 1
fi

# Assign the arguments to variables
validated_recs_path="$1"
dict_file_path="$2"
acs_mod_path="$3"
output_path="$4"

# Find all subfolders
subfolders=$(find "$validated_recs_path" -mindepth 1 -maxdepth 1 -type d | sort)

# Loop through all subfolders
for subfolder in $subfolders; do
    echo -e "\nProcessing subfolder: $subfolder\n"
    # Execute the mfa align --clean command for each subfolder
    mfa align --clean "$subfolder" "$dict_file_path" "$acs_mod_path" "$output_path"
done

end=$(date +%s)  # Gets the current Unix timestamp in seconds again

duration=$((end - start))  # Duration in seconds

echo -e "\nAll subfolders aligned. Total run time was $duration seconds.\n"
