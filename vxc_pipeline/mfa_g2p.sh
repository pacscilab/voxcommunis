#!/bin/bash

# This is a script to split the large word list file into smaller splits, each with 32000 words and use the MFA G2P model to convert them into IPA transcriptions.
# Created by Miao Zhang, 24.05.2024

# Capture the start time
start_time=$(date +%s)

# Check if the user provided the input file and G2P model path as arguments
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 filename g2p_model_path"
    exit 1
fi

input_file="$1"
g2p_model_path="$2"

# Check if the input file exists
if [ ! -f "$input_file" ]; then
    echo "File not found!"
    exit 1
fi

# Check if the G2P model path exists
if [ ! -f "$g2p_model_path" ]; then
    echo "G2P model file not found!"
    exit 1
fi

# Get the directory path and base name of the input file
input_dir=$(dirname "$input_file")
base_name=$(basename "$input_file")

# Replace 'wordlist' with 'lexicon' in the input file name
output_base_name="${base_name/wordlist/lexicon}"

# Create a new directory in the same directory as the input file (without extension) to contain the smaller files
output_dir="${input_dir}/${output_base_name%.*}_split"
mkdir -p "$output_dir"

# Initialize variables
lines_per_file=32000
file_count=0
line_count=0

# Function to create a new output file
create_new_file() {
    file_count=$((file_count + 1))
    formatted_count=$(printf "%02d" "$file_count")
    out_filename="${output_dir}/${output_base_name%.*}_${formatted_count}.txt"
    > "$out_filename"  # Create/truncate the file
}

create_new_file  # Create the first output file

# Split the file manually
while IFS= read -r line; do
    line_count=$((line_count + 1))
    
    if (( line_count > lines_per_file )); then
        line_count=1
        create_new_file
    fi
    
    echo "$line" >> "$out_filename"
done < "$input_file"

# Initialize a file to hold the merged G2P output
merged_g2p_output="${input_dir}/${output_base_name%.*}.txt"
> "$merged_g2p_output"  # Create/truncate the file

# Run the 'mfa g2p' command on each of the smaller files and merge the outputs
for small_file in "${output_dir}"/*.txt; do
    output_g2p_file="${small_file%.txt}_g2p.txt"
    mfa g2p "$small_file" "$g2p_model_path" "$output_g2p_file"
    cat "$output_g2p_file" >> "$merged_g2p_output"
done

# Delete the directory containing the split files
rm -r "$output_dir"

# Capture the end time
end_time=$(date +%s)

# Calculate the duration
duration=$((end_time - start_time))

# Print the message
echo ""
echo "G2P conversion done, check the results in: $merged_g2p_output."
echo "Total run time: $duration seconds."
echo ""