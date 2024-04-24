import re, csv, subprocess, unicodedata, os, shutil, zipfile, tarfile, multiprocessing
import pandas as pd
import numpy as np
from praatio import textgrid
from pathlib import Path


##########################################################################################################
##########################################################################################################

# Remap speakers and generate a speaker file
def remap_spkr(lang_dir, spkr_file_path, lang_code, output=True):
    clip_dir = os.path.join(lang_dir, 'clips') # Where all the clips are
    invalid_log = os.path.join(lang_dir, 'invalidated.tsv') # where the invalidated utterance log of common voice is
    valid_log = os.path.join(lang_dir, 'validated.tsv') # where the validated utterance log of common voice is
    clip_dur_file = os.path.join(lang_dir, 'clip_durations.tsv') # where the clip duration file is

    invalidated = pd.read_csv(invalid_log, sep = '\t', quoting=csv.QUOTE_NONE, low_memory = False,
                          dtype = {
                              'client_id': 'str',
                              'path': 'str',
                              'sentence': 'str',
                              'up_votes': 'int16',
                              'down_votes': 'int16',
                              'age': 'str',
                              'gender': 'str',
                              'accentes': 'str',
                              'variant': 'str',
                              'locale': 'str',
                              'segment': 'str'
                          })
    validated = pd.read_csv(valid_log, sep = '\t', quoting=csv.QUOTE_NONE, low_memory = False,
                            dtype = {
                                'client_id': 'str',
                                'path': 'str',
                                'sentence': 'str',
                                'up_votes': 'int16',
                                'down_votes': 'int16',
                                'age': 'str',
                                'gender': 'str',
                                'accentes': 'str',
                                'variant': 'str',
                                'locale': 'str',
                                'segment': 'str'
                            })
    invalidated['validation'] = 'invalidated'
    validated['validation'] = 'validated'
    whole = pd.concat([validated, invalidated], axis=0)
    del invalidated, validated

    # Skip the clients whose data are deleted on Common Voice
    with open('speaker_skiplist.txt', 'r') as skip:
        speaker_skiplist = [line.strip() for line in skip.readlines()] # get the client ids that need to be skipped
    whole = whole[~whole['client_id'].isin(speaker_skiplist)]

    # Get the clip durations
    clip_dur = pd.read_csv(clip_dur_file, sep = '\t',
                        dtype = {'clip': 'str', 'duration[ms]': 'float64'})
    clip_dur.rename(columns = {'clip':'path', 'duration[ms]':'dur'}, inplace=True)
    clip_dur.set_index('path', inplace = True)

    # Append duration info to validated speaker file
    whole.set_index('path', inplace = True)
    whole = pd.concat([whole, clip_dur], axis = 1, join = 'inner')
    whole['dur'] = whole['dur']/1000
    whole.reset_index(inplace=True)
    del clip_dur

    # Create a column that shows if the clip is validated or not based on the votes
    conditions = [
        ((whole['validation'] == 'validated') & (whole['dur'] > 1)),
        (whole['validation'] == 'invalidated'),
        (
            ((whole['validation'] == 'validated') & (whole['dur'] <= 1)) |
            (whole['sentence'] == '') |
            (whole['sentence'].isna()) |
            (whole['sentence'].str.contains('common_voice', regex=True))
            ),
    ]
    choices = ["validated", "invalidated", "other"]
    whole["validation"] = np.select(conditions, choices)
    del conditions, choices

    # remap the speakers:
    whole['speaker_id'] = pd.factorize(whole['client_id'])[0] + 1
    whole['speaker_id'] = whole.speaker_id.astype('str')

    # subset the data to only validated recordings
    whole = whole[whole['validation'] == 'validated']
    whole.drop('validation', axis = 1, inplace = True)

    # Tokenize Japanese texts
    if lang_code == 'ja':
        # Import the Japanese tokenizer
        from fugashi import Tagger
        tagger = Tagger('-Owakati')
        jpn_sentences = whole['sentence'].astype('str').tolist()
        tokenized = pd.Series([tagger.parse(sentence) for sentence in jpn_sentences])
        tokenized = tokenized.str.replace('([っ|ん]) ([て｜で｜た｜だ])', "\\1\\2", regex = True)
        tokenized = tokenized.str.replace(' ん', 'ん')

        whole['sentence'] = tokenized

    # save the speaker file
    if output:
        if os.path.exists(spkr_file_path):
            os.remove(spkr_file_path)
        whole.to_csv(spkr_file_path, sep='\t', index=False)

    # The file paths
    paths = whole['path'].tolist()
    whole['src_path'] = [os.path.join(clip_dir, path) for path in paths]
    whole['new_path'] = [os.path.join(lang_dir, 'validated', path) for path in paths]
    
    # If there are more than 32000 files, split them into groups and create paths in the subfolders
    n_clips = len(whole)
    if n_clips > 32000:
        group_size = 32000
        root = os.path.join(lang_dir, 'validated')
        num_groups = (n_clips + group_size - 1) // group_size
        whole['subfolder'] = ["subfolder_" + str(i+1).zfill(3) for i in range(num_groups) for _ in range(min(32000, n_clips - i*32000))]
        whole['sub_path'] = [os.path.join(root, i, j) for i, j in zip(whole.subfolder, whole.path)]
        valid = whole[['path', 'src_path', 'new_path', 'subfolder', 'sub_path', 'speaker_id', 'dur', 'sentence']]
    else:
        valid = whole[['path', 'src_path', 'new_path', 'speaker_id', 'dur', 'sentence']]
    
    return valid

##########################################################################################################
##########################################################################################################

# The function to create the textgrid files
def create_textgrid(snd_file, dur, speaker_id, transcript):
    # Create the textgrid
    tg = textgrid.Textgrid()
    # Add a new tier to the TextGrid
    speaker_tier = textgrid.IntervalTier(speaker_id, # tier name
                                        [(0.05, dur-0.05, transcript)], # interval start time, end time, and the transcript
                                        0, # start time
                                        dur) # end time
    tg.addTier(speaker_tier)
    # Save the TextGrid to a file
    snd_path = Path(snd_file)
    tg_filename = snd_path.with_suffix('.TextGrid')
    tg.save(tg_filename, format='short_textgrid', includeBlankSpaces=True)

def move_and_create_tg(df):
    for src_mp3_path, new_path, speaker, dur, transcript in zip(df.src_path, df.new_path, df.speaker_id, df.dur, df.sentence):
        src_mp3_path = Path(src_mp3_path)
        new_path = Path(new_path)
        # Copy sound file and crate the textgrid file  
        if src_mp3_path.exists():
            try:
                shutil.move(src_mp3_path, new_path)
            except Exception as e:
                print(f"File moving error: {e}")
            # Get the textgrid file name
            tg_filename = new_path.with_suffix('.TextGrid')
            if not os.path.exists(tg_filename):
                create_textgrid(new_path, dur, speaker, transcript)


##########################################################################################################
##########################################################################################################


# Get words from transcripts:
def process_words(log, lang_code):
    # Read in the validated.tsv file and get the orthographical transcriptions of the utterances
    words = pd.read_csv(log, sep='\t', low_memory = False, usecols = ['sentence'], dtype = {'sentence':'str'}) # get the transcribed sentences
    # Filter out rows where the transcript is missing.
    words = words[words['sentence'].notnull()]['sentence']

    # Remove the punctuations
    words = words.str.replace('[՜|։|՝|՛|।|›|‹|/|\(|\)|\[|\]|,|‚|።|፡|፣|.|،|!|?|+|\"|″|″|×|°|¡|“|⟨|⟩|„|→|‑|–|-|-|−|-|—|‒|۔|\$|ʻ|ʿ|ʾ|`|´|’|‘|«|»|;|؛|:|”|؟|&|\%|…|\t|\n| \' ]+', ' ', regex=True)
    # Remove the arabic punctuations and combining marks
    words = words.str.replace('[ء| ؓ| ؑ]+', ' ', regex=True)
    # Remove all numbers
    words = words.str.replace('[0-9]+', ' ', regex=True)
    # Remove all remaining punctuations
    words = words.str.replace('[[:punct:]]+', ' ', regex=True)
    # Merge multiple continueing white spaces
    words = words.str.replace('[ ]+', ' ', regex=True)
    # To lower case
    words = words.str.lower()

    # Make it a list of the word types
    words.tolist()
    words = ' '.join(words)
    words = words.split(' ')
    words = sorted(set(words))
    words = [word for word in words if word.strip()]
    words = list(filter(None, words))
    

    # Filter out some text errors from Common Voice
    words = [re.sub('^mp3', '', word) for word in words]
    words = [word for word in words if 'common_voice' not in word]

    return words

# Keep only the first unique strings
def keep_first_unique_strings(strings):
    seen = set()
    result = []
    for string in strings:
        words = string.split()  # Split the string into words
        unique_string = " ".join(words)  # Reconstruct the string
        if unique_string not in seen:
            result.append(unique_string)
            seen.add(unique_string)
    return result

##########################################################################################################
##########################################################################################################

# Move the recordings in and out of subfolders when the corpus is too large (more than 32000 recordings)
def split_recs(df):
    df = df
    for src_snd, sub_snd in zip(df.new_path, df.sub_path):
        src_tg = Path(src_snd).with_suffix('.TextGrid')
        sub_tg = Path(sub_snd).with_suffix('.TextGrid')
        try:
            shutil.move(src_snd, sub_snd)
            shutil.move(src_tg, sub_tg)
        except Exception as e:
            print(f"File moving error: {e}")

# Merge the recordings back
def merge_recs(df):
    df = df
    for src_snd, sub_snd in zip(df.sub_path, df.new_path):
        src_tg = Path(src_snd).with_suffix('.TextGrid')
        sub_tg = Path(sub_snd).with_suffix('.TextGrid')
        try:
            shutil.move(src_snd, sub_snd)
            shutil.move(src_tg, sub_tg)
        except Exception as e:
            print(f"File moving error: {e}")

# Move the files failed to be put back to the root directory
def move_files_to_root(rootdir, subdir):
    # List all files in the subdirectory
    subdir = os.path.join(rootdir, subdir)
    files_to_move = os.listdir(subdir)

    moved_files = []
    failed_files = []
    # Move each file to the root folder
    for file_name in files_to_move:
        # Get the full path of the file in the subdirectory
        src = os.path.join(subdir, file_name)
        tgt = os.path.join(rootdir, file_name)
        # Move the file to the root folder
        try:
            shutil.move(src, tgt)
            moved_files.append(file_name)
        except Exception as e:
            # Handle any errors
            failed_files.append((file_name, str(e)))

    report = {}
    report['moved_files'] = moved_files
    report['failed_files'] = failed_files
    report['files_left_in_subfolder'] = os.listdir(subdir)

    return report

# Check if there are file overlaps across subfolders
def check_file_overlaps(root_dir):
    # Dictionary to store file names and their paths
    file_dict = {}

    # Iterate over subfolders
    for dirpath, _, filenames in os.walk(root_dir):
        # Iterate over files in the subfolder
        for filename in filenames:
            # Get the full path of the file
            file_path = os.path.join(dirpath, filename)
            # Check if the file name already exists in the dictionary
            if filename in file_dict:
                # If it exists, append the current file path to the list of paths
                file_dict[filename].append(file_path)
            else:
                # If it doesn't exist, create a new entry with the file name and its path
                file_dict[filename] = [file_path]

    # Dictionary to store overlapping file names and their paths
    overlap_dict = {}

    # Check for file name overlaps
    for filename, file_paths in file_dict.items():
        if len(file_paths) > 1:
            overlap_dict[filename] = file_paths

    return overlap_dict

# Search a file
def search_files(directory, search_string):
    found_files = []
    # Traverse the directory structure
    for root, dirs, files in os.walk(directory):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            # Try different encodings to read the file
            for encoding in ['utf-8', 'latin-1']:  # Add more encodings if needed
                try:
                    # Open each file with the specified encoding
                    with open(file_path, 'r', encoding=encoding) as file:
                        if search_string in file.read():
                            found_files.append(file_path)
                    # Break the loop if the file is successfully read
                    break
                except UnicodeDecodeError:
                    # If decoding fails, try the next encoding
                    continue
    return found_files

# Check if the input and output match
def compare_inout(output, input):
    all_outputs = set(os.path.splitext(item)[0] for item in os.listdir(output))
    all_inputs = set(os.path.splitext(item)[0] for item in os.listdir(input) if item.endswith('.mp3'))

    n_output = len(all_outputs)
    n_input = len(all_inputs)
    print(f"There are {n_input} mp3 files in the validated folder.")
    print(f"There are {n_output} textgrid files in the output folder.")

    if n_output != n_input:
        return False, "Number of files in validated and output folders is different."

    if all_outputs != all_inputs:
        # Find mismatched files using set operations
        mismatched_files = all_outputs.symmetric_difference(all_inputs)
        return False, "File names in validated and the output folders do not match.", list(mismatched_files)

    return True, "The recordings in the validated folder and the textgrids in the output folder match."

# zip the output textgrids
# load the file as a string then add it to the zip in a thread safe manner
def add_file(lock, handle, filepath, base_folder):
    # load the data as a string
    with open(filepath, 'r') as file_handle:
        data = file_handle.read()
    # get the relative path
    rel_path = os.path.relpath(filepath, base_folder)
    # add data to zip
    with lock:
        handle.writestr(rel_path, data)
    # report progress
    #print(f'.added {filepath}')

# Check if the folder contains not just subdirectories but also files
def contains_files(folder_path):
    # Get a list of all items (files and folders) in the specified folder
    all_items = os.listdir(folder_path)

    # Check if there are any files in the folder
    for item in all_items:
        item_path = os.path.join(folder_path, item)
        if os.path.isfile(item_path):
            # If we find at least one file, return True
            return True

    # If no files were found, return False
    return False
 


############################################################
################### Text processing ########################
############################################################

# Filter Serbian
def is_serbian_word(word):
    # Regular expression to match Serbian letters (Cyrillic and Latin alphabets)
    serbian_pattern = re.compile(r'^[а-яА-ЯјЈљЉњЊђЂчЧћЋшШжЖгГѕЅцЦџЏ]+$', re.IGNORECASE)

    # Check if the word contains only Serbian letters
    return bool(serbian_pattern.match(word))
def remove_non_serbian(words):
    return [word for word in words if is_serbian_word(word)]

# Filter Bengali
def is_bengali(word):
    # Bengali Unicode range: U+0980 to U+09FF
    bengali_range = re.compile(r'[\u0980-\u09FF]+')
    return bool(bengali_range.match(word))

# Filter Turkish
def is_turkish_word(word):
    # Match Turkish letters using regular expression
    turkish_letters_pattern = re.compile(r'^[a-zA-ZğüşıöçĞÜŞİÖÇ]+$')
    return bool(turkish_letters_pattern.match(word))
def remove_non_turkish(word_list):
    return [word for word in word_list if is_turkish_word(word)]

# Filter Abkhaz
def is_abkhaz_word(word):
    abkhaz_characters = {'а', 'аҧ', 'б', 'в', 'г', 'гь', 'д', 'е', 'еи', 'еӡ', 'ж', 'з', 'и', 'иҭ', 'иҵ', 'й', 
    'к', 'кь', 'л', 'м', 'н', 'о', 'оа', 'оҧ', 'ои', 'оиа', 'оиҧ', 'оиҳ', 'оиӡ', 'п', 'пс', 'р', 'с', 'т', 'у', 
    'ф', 'х', 'ц', 'ч', 'чӡ', 'ш', 'щ', 'ъ', 'ы', 'ь', 'э', 'ю', 'я', 'ҕ', 'ҳ', 'ҟ', 'ҟӡ', 'ҭ', 'ҵ', 'ҷ', 'ҽ', 'ҽа', 'ҽы', 'ҽь', 'ҽӡ'}
    # Check if all characters in the word belong to Abkhaz characters
    return all(char in abkhaz_characters for char in word)
def remove_non_abkhaz(word_list):
    abkhaz_word_list = [word for word in word_list if is_abkhaz_word(word)]
    return abkhaz_word_list

# Filter Catalan
def contains_non_catalan_letters(word):
    # Catalan alphabet consists of characters from a-z, A-Z, à-ü, and special characters used in Catalan
    catalan_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZàÀáÁèÈéÉíÍïÏòÒóÓúÚüÜçÇ"
    return any(char not in catalan_letters for char in word)
def remove_non_catalan(word_list):
    catalan_word_list = [word for word in word_list if not contains_non_catalan_letters(word)]
    return catalan_word_list


# Filter Dutch
def is_dutch_word(word):
    dutch_letters = [
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
    'à', 'á', 'â', 'ã', 'ä', 'å', 'æ', 'ç', 'è', 'é', 'ê', 'ë', 'ì', 'í', 'î', 'ï', 'ð', 'ñ', 'ò', 'ó', 'ô', 'õ', 'ö', 'ø', 'ù', 'ú', 'û', 'ü', 'ý', 'þ', 'ÿ']
    # Check if all characters in the word belong to Dutch letters
    return all(char in dutch_letters for char in word)
def remove_non_dutch(word_list):
    dutch_word_list = [word for word in word_list if is_dutch_word(word)]
    return dutch_word_list

# Filter Bashkir
def is_bashkir_word(word):
    bashkir_letters = set([
    'А', 'а',  # A
    'Ә', 'ә',  # Ä
    'Б', 'б',  # B
    'В', 'в',  # V
    'Г', 'г',  # G
    'Ғ', 'ғ',  # Ğ
    'Д', 'д',  # D
    'Е', 'е',  # E
    'Ё', 'ё',  # Yo
    'Ж', 'ж',  # J
    'З', 'з',  # Z
    'И', 'и',  # I
    'Й', 'й',  # Y
    'К', 'к',  # K
    'Ҡ', 'ҡ',  # Q
    'Л', 'л',  # L
    'М', 'м',  # M
    'Н', 'н',  # N
    'Ң', 'ң',  # Ñ
    'О', 'о',  # O
    'Ө', 'ө',  # Ö
    'П', 'п',  # P
    'Р', 'р',  # R
    'С', 'с',  # S
    'Т', 'т',  # T
    'У', 'у',  # U
    'Ү', 'ү',  # Ü
    'Ф', 'ф',  # F
    'Х', 'х',  # H
    'Һ', 'һ',  # H with a hook
    'Ц', 'ц',  # Ts
    'Ч', 'ч',  # Ch
    'Ш', 'ш',  # Sh
    'Щ', 'щ',  # Shch
    'Ъ', 'ъ',  # Hard sign
    'Ы', 'ы',  # Y
    'Ь', 'ь',  # Soft sign
    'Э', 'э',  # E
    'Ю', 'ю',  # Yu
    'Я', 'я',  # Ya
])
    return all(char in bashkir_letters for char in word)
def remove_non_bashkir(word_list):
    return [word for word in word_list if is_bashkir_word(word)]

# Filter indonesian
def contains_indonesian_letters(word):
    # Define Unicode character ranges for Indonesian letters
    indonesian_alphabet_ranges = [
        (0x0041, 0x005A),  # Latin uppercase letters A-Z
        (0x0061, 0x007A),  # Latin lowercase letters a-z
        (0x00C0, 0x00FF),  # Latin extended-A letters with diacritics
        (0x0100, 0x017F),  # Latin extended-B letters with diacritics
    ]
    # Check if all characters in the word fall within the defined ranges
    for char in word:
        char_code = ord(char)
        if not any(start <= char_code <= end for start, end in indonesian_alphabet_ranges):
            return False
    return True
def remove_non_ind(word_list):
    ind_word_list = [word for word in word_list if contains_indonesian_letters(word)]
    return ind_word_list


# Filter Hausa
def is_hausa_word(word):
    haus_characters = {'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 
    's', 't', 'u', 'v', 'w', 'x', 'y', 'z', 'ɓ', 'ɗ', 'ƙ', 'ƴ'}
    # Check if all characters in the word belong to Hausa characters
    return all(char in haus_characters for char in word)
def remove_non_hausa(word_list):
    haus_word_list = [word for word in word_list if is_hausa_word(word)]
    return haus_word_list


# Filter Hindi
def is_hindi_word(word):
    hindi_characters = {'अ', 'आ', 'इ', 'ई', 'उ', 'ऊ', 'ऋ', 'ए', 'ऐ', 'ओ', 'औ', 'क', 'ख', 'ग', 'घ', 'ङ', 'च', 'छ', 
    'ज', 'झ', 'ञ', 'ट', 'ठ', 'ड', 'ढ', 'ण', 'त', 'थ', 'द', 'ध', 'न', 'प', 'फ', 'ब', 'भ', 'म', 'य', 'र', 'ल', 'व', 'श', 
    'ष', 'स', 'ह', 'क्ष', 'त्र', 'ज्ञ', 'ं', 'ः', 'ँ', '़', '।', '॥', 'ऽ', '्', 'ा', 'ि', 'ी', 'ु', 'ू', 'ृ', 'ॅ', 'ॆ', 'े', 'ै', 'ॉ', 'ॊ', 'ो', 'ौ', '्र', 'ःं'}
    # Check if all characters in the word belong to Hindi characters
    return all(char in hindi_characters for char in word)
def remove_non_hindi(word_list):
    hindi_word_list = [word for word in word_list if is_hindi_word(word)]
    return hindi_word_list



    
# Filter out unwanted CJK characters in non-CJK texts
def is_cjk(char):
    # Check if the character is a CJK character
    return bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]', char))
def remove_cjk(words):
    # Use list comprehension to filter out words containing CJK or non-Latin letters
    filtered_words = [word for word in words if all(not is_cjk(char) for char in word)]
    filtered_words = list(filter(None, filtered_words))
    return filtered_words



# Filter out non-Greek words
def is_greek_letter(char):
    # Check if the character is a Greek letter
    return char.isalpha() and ('\u0370' <= char <= '\u03FF' or '\u1F00' <= char <= '\u1FFF')
def remove_non_greek(greek_words):
    # Use list comprehension to filter out words containing non-Greek letters
    filtered_words = [word for word in greek_words if all(is_greek_letter(char) for char in word)]
    filtered_words = list(filter(None, filtered_words))
    return filtered_words

# Filter out non-Hungarian
def contains_hungarian_letters(word):
    # Hungarian alphabet consists of characters from a-z, A-Z, and á-ű
    return bool(re.match('^[a-zA-ZáéíóöőúüűÁÉÍÓÖŐÚÜŰ]+$', word))
def remove_non_hungarian(word_list):
    hungarian_words_only = [word for word in word_list if contains_hungarian_letters(word)]
    return hungarian_words_only


# Filter out non-Ukrainian
def is_ukrainian_word(word):
    ukrainian_alphabet_ranges = [
    (0x0430, 0x044F),  # Lowercase Cyrillic letters а-я
    (0x0451, 0x0451),  # Lowercase ё
    (0x0454, 0x0454),  # Lowercase є
    (0x0456, 0x0456),  # Lowercase і
    (0x0457, 0x0457),  # Lowercase ї
    (0x0491, 0x0491)]  # Lowercase ґ
    for char in word:
        char_code = ord(char)
        if not any(start <= char_code <= end for start, end in ukrainian_alphabet_ranges):
            return False
    return True
def remove_non_ukr(word_list):
    ukrainian_words_only = [word for word in word_list if is_ukrainian_word(word)]
    return ukrainian_words_only

# Filter out non-Uyghur
def remove_non_uig(words):
    # Define Unicode character ranges for Uighur letters
    uighur_alphabet_ranges = [
        (0x0600, 0x06FF),  # Uighur Arabic script
    ]
    # Construct regex pattern
    uighur_regex_pattern = '['
    for start, end in uighur_alphabet_ranges:
        uighur_regex_pattern += f'\\u{start:04X}-\\u{end:04X}'
    uighur_regex_pattern += ']'
    # Compile regex pattern
    uighur_regex = re.compile(uighur_regex_pattern)
    # Filter out non-Uighur words
    uighur_words_only = [word for word in words if uighur_regex.match(word)]
    return uighur_words_only



# Filter out non-German words
def is_german_word(word):
    # Check if the word contains only German letters
    german_letters = set("abcdefghijklmnopqrstuvwxyzäöüßÄÖÜ")
    return all(char in german_letters for char in word)
def remove_non_german(german_words):
    # Use list comprehension to filter out non-German words
    filtered_words = [word for word in german_words if is_german_word(word)]
    filtered_words = list(filter(None, filtered_words))
    return filtered_words


# Filter out non-Vietnamese words:
def is_vietnamese(word):
    vietnamese_characters = "aăâbcdđeêghiklmnoôơpqrstuưvxyáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
    for char in word:
        if char not in vietnamese_characters:
            return False
    return True
def remove_non_vietnamese_letter(words):
    return [word for word in words if is_vietnamese(word)]
def remove_non_vietnamese(words):
    filtered_words = [word for word in remove_non_vietnamese_letter(words) if not any(char.isdigit() for char in word)]
    filtered_words = list(filter(None, filtered_words))
    return filtered_words

# Filter out non-Urdu words
def remove_non_urdu(word_list):
    # Unicode range for Urdu characters
    urdu_pattern = re.compile('[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]+')
    urdu_words = [word for word in word_list if urdu_pattern.search(word)]
    filtered_words = list(filter(None, urdu_words))
    return filtered_words

# Filter out non-Czech words
def is_czech_word(word):
    # Define a regular expression pattern for Czech letters
    czech_pattern = re.compile(r'^[aábcčdďeéěfghchiíjklmnňoópqrřsštťuúůvwxyýzžAÁBCČDĎEÉĚFGHCHIÍJKLMNŇOÓPQRŘSŠTŤUÚŮVWXYÝZŽ]+$')
    # Check if the word matches the Czech pattern
    return bool(czech_pattern.match(word))
def remove_non_czech(word_list):
    return [word for word in word_list if is_czech_word(word)]



# Filter out unwanted words for Common Voice languages:
def remove_unwanted_words(word_list, lang_code, if_cjk):
    # Filter out unwanted CJK words
    if if_cjk == 0:
        filtered_words = remove_cjk(word_list)
        
    # Filter out other unwanted words on a by-language base
    if lang_code == 'de': # filter German
        filtered_words = remove_non_german(filtered_words)
    elif lang_code == 'el': # filter Greek
        filtered_words = remove_non_greek(filtered_words)
    elif lang_code == 'ur': # filter Urdu
        filtered_words = remove_non_urdu(filtered_words)
    elif lang_code == 'vi': # filter Vietnamese
        filtered_words = remove_non_vietnamese(filtered_words)
    elif lang_code == 'ab': # filter Abkhaz
        filtered_words = remove_non_abkhaz(filtered_words)
    elif lang_code == 'ha': # filter Hausa
        filtered_words = remove_non_hausa(filtered_words)
    elif lang_code == 'hi': # filter Hindi
        filtered_words = remove_non_hindi(filtered_words)
    elif lang_code == 'nl': # filter Dutch
        filtered_words = remove_non_dutch(filtered_words)
    elif lang_code == 'uk': # filter Ukrainian
        filtered_words = remove_non_ukr(filtered_words)
    elif lang_code == 'ug': # filter Uighur
        filtered_words = remove_non_uig(filtered_words)
    elif lang_code == 'hu': # filter Hungarian
        filtered_words = remove_non_hungarian(filtered_words)
    elif lang_code == 'id': # filter Indonesian
        filtered_words = remove_non_ind(filtered_words)
    elif lang_code == 'ba': # filter Bashkir
        filtered_words = remove_non_bashkir(filtered_words)
    elif lang_code == 'cs': # filter Czech
        filtered_words = remove_non_czech(filtered_words)
    elif lang_code == 'ca': # filter Catalan
        filtered_words = remove_non_catalan(filtered_words)
    elif lang_code == 'tr': # filter Turkish
        filtered_words = remove_non_turkish(filtered_words)
    elif lang_code == 'ru': # filter Russian
        filtered_words = [word for word in filtered_words if re.match(r'^[а-яА-ЯёЁ]+$', word)]
    elif lang_code == 'bn': # filter Bengali
        filtered_words = [word for word in filtered_words if is_bengali(word)]
    elif lang_code == 'sr':
        filtered_words = remove_non_serbian(filtered_words)

    return filtered_words