# Import modules
import os, re, csv, sys
import pandas as pd
# Turn Copy-On-Write on
pd.options.mode.copy_on_write = True
import numpy as np


def get_codes(lang_code):
    cv_tracking_file = 'VoxCommunis_Info.csv'
    with open(cv_tracking_file, 'r') as f:
        reader = csv.DictReader(f)
        lang_row = [row for row in reader if row['code_cv'] == lang_code][0]
    
    return lang_row

# Function to find directories with a specific prefix and specific digit count
def find_lang_dir(lang_code, ver, common_voice_dir):
    # Regular expression pattern to match folders starting with the language code followed by '_v' and a specific version number
    pattern = r'^{}_v{}$'.format(re.escape(lang_code), ver)

    # List all entries in Common Voice folder
    matched_folders = [folder for folder in os.listdir(common_voice_dir)
                       if os.path.isdir(os.path.join(common_voice_dir, folder)) and re.match(pattern, folder)]
    if len(matched_folders) == 0:
        print(f'Could not find the folder {lang_code}_v{ver} in {common_voice_dir}')
    else:
        folder_path = os.path.join(common_voice_dir, matched_folders[0])
        clip_info_path = os.path.join(folder_path, 'clip_durations.tsv')
        validated_log = os.path.join(folder_path, 'validated.tsv')
        validated_recs_path = os.path.join(folder_path, 'validated')
        
        return folder_path, clip_info_path, validated_log, validated_recs_path


def detect_cjk(lang_code):
    is_cjk = lang_code in ['ja', 'ko', 'yue', 'zh-CN', 'zh-HK', 'zh-TW', 'nan-tw']

def show_files(language_dir, acs_mod_path, dict_file_path, spkr_file_path, textgrid_folder_path):
    print("Processing the folder:\t", language_dir)
    print("The acoustic model to be trained/used:\t", acs_mod_path)
    print("The lexicon to be generated/used:\t", dict_file_path)
    print("The speaker file to be generated:\t", spkr_file_path)
    print("The archive of the textgrids to be generated:\t", textgrid_folder_path)