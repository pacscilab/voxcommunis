# Input file names
file1 = "/Users/miaozhang/Research/CorpusPhon/CorpusData/CommonVoice/zh-HK_v17/zh-HK_epi_lexicon17.txt"
file2 = "/Users/miaozhang/Research/CorpusPhon/CorpusData/CommonVoice/yue_v17/yue_epi_lexicon17.txt"
output_file = "/Users/miaozhang/Research/CorpusPhon/CorpusData/CommonVoice/yue_v17/cantonese_epi_lexicon17.txt"

# Read and store lines from file1 and file2 without duplicates
lines_seen = set()
all_lines = []

for infile in [file1, file2]:
    with open(infile, "r") as file:
        for line in file:
            if line.strip() not in lines_seen:
                lines_seen.add(line.strip())
                all_lines.append(line)

# Write unique and sorted lines to the output file
with open(output_file, "w") as outfile:
    sorted_lines = sorted(set(all_lines))
    outfile.writelines(sorted_lines)