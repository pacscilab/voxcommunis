import re, csv, subprocess, unicodedata, os, shutil
import pandas as pd
import numpy as np
from praatio import textgrid
from pathlib import Path

##########################################################################################################
##########################################################################################################

# Remap speakers and generate a speaker file
def remap_spkr(lang_dir, path_sep, spkr_file_path):
    clip_dir = lang_dir + path_sep + 'clips' + path_sep # Where all the clips are
    invalid_log = lang_dir + path_sep + 'invalidated.tsv' # where the invalidated utterance log of common voice is
    valid_log = lang_dir + path_sep + 'validated.tsv' # where the validated utterance log of common voice is
    clip_dur_file = lang_dir + path_sep + 'clip_durations.tsv' # where the clip duration file is

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
    #speaker_lab = whole['speaker_id'].str.zfill(5)
    #whole['new_utt'] = speaker_lab + '_' + whole['path']

    # save the speaker file
    if os.path.exists(spkr_file_path):
        os.remove(spkr_file_path)
    whole.to_csv(spkr_file_path, sep='\t', index=False)

    # The file paths
    whole['src_path'] = clip_dir + whole['path']

    cond_snd_path = [
        (whole['validation'] == 'validated'),
        (whole['validation'] == 'invalidated'),
        (whole['validation'] == 'other'),
    ]
    choice_snd_path = [lang_dir + path_sep + 'validated' + path_sep + whole['path'],  
                       lang_dir + path_sep + 'clips' + path_sep + whole['path'],
                       lang_dir + path_sep + 'other' + path_sep + whole['path'],]
    whole["new_path"] = np.select(cond_snd_path, choice_snd_path)
    whole = whole[['src_path', 'new_path', 'speaker_id', 'dur', 'sentence', 'validation']]

    return whole

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
    for src_mp3_path, new_path, speaker, dur, transcript, validation in zip(df.src_path, df.new_path, df.speaker_id, df.dur, df.sentence, df.validation):
        src_mp3_path = Path(src_mp3_path)
        new_path = Path(new_path)
        # Copy sound file and crate the textgrid file  
        if validation != 'invalidated' and src_mp3_path.exists():
            shutil.move(src_mp3_path, new_path)
            tg_filename = new_path.with_suffix('.TextGrid')
            if validation == 'other' or isinstance(transcript, float):
                os.remove(new_path)
            elif not os.path.exists(tg_filename):
                create_textgrid(new_path, dur, speaker, transcript)



##########################################################################################################
##########################################################################################################


# Get words from transcripts:
def process_words(validated_log):
    # Read in the validated.tsv file and get the orthographical transcriptions of the utterances
    words = pd.read_csv(validated_log, sep='\t', low_memory = False, usecols = ['sentence'], dtype = {'sentence':'str'}) # get the transcribed sentences
    # Filter out rows where the transcript is missing.
    words = words[words['sentence'].notnull()]['sentence']

    # Remove the punctuations
    words = words.str.replace('[›|‹|\(|\)|\[|\]|,|‚|.|،|!|?|+|\"|″|″|×|°|¡|“|⟨|⟩|„|→|‑|–|-|-|−|-|—|‒|۔|\$|ʻ|ʿ|ʾ|`|´|’|‘|«|»|;|؛|:|”|؟|&|\%|…|\t| \' ]+', ' ', regex=True)
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
    words = list(filter(None, words))

    # Filter out some text errors from Common Voice
    words = [re.sub('^mp3', '', word) for word in words]
    words = [word for word in words if 'common_voice' not in word]

    return words
                


############################################################
################### Text processing ########################
############################################################

# Functions:
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
    hungarian_words_only = [word for word in hungarian_words if contains_hungarian_letters(word)]
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
    elif lang_code == 'cs':
        filtered_words = remove_non_czech(filtered_words)

    return filtered_words