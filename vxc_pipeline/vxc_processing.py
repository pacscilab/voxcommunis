import re, csv, subprocess, unicodedata, os, shutil, zipfile, tarfile, multiprocessing
import pandas as pd
import numpy as np
from praatio import textgrid
from pathlib import Path
# Multithread pool
from concurrent.futures import ThreadPoolExecutor


# Japanese tokenizer
from fugashi import Tagger
# Korean tokenizer
from konlpy.tag import Okt
# Cantonese tokenizer
import pycantonese
# Traditional Chinese tokenizer
from ckiptagger import WS
# Simplified Chinese tokenizer and processing
import pkuseg
import chinese_converter
# For Chinese G2P
from pypinyin import pinyin, Style
from pinyin_to_ipa import pinyin_to_ipa

# Tokenize IPA
from lingpy import ipa2tokens

##########################################################################################################
##########################################################################################################

# The function to tokenize CJK languages:
def tok_cjk(df, lang_code):
    if lang_code == 'ja':
        tagger = Tagger('-Owakati')
        tokenized = [tagger.parse(sentence) for sentence in df['sentence'].astype('str').tolist()]
        tokenized = [re.sub(r'([っ|ん]) ([て｜で｜た｜だ])', r"\1\2", sentence) for sentence in sentences]
        tokenized = [re.sub(r' (ん)', r'\1', sentence) for sentence in sentences]
    
    # Korean
    elif lang_code == 'ko':
        okt = Okt()
        tokenized = [' '.join(okt.morphs(sentence)) for sentence in df['sentence'].astype('str').tolist()]
    
    # Cantonese
    elif lang_code in ['yue', 'zh-HK']:
        tokenized = [' '.join(pycantonese.segment(sentence)) for sentence in df['sentence'].astype('str').tolist()]
    
    # Simplified Chinese
    elif lang_code == 'zh-CN':
        seg = pkuseg.pkuseg()
        tokenized = [' '.join(seg.cut(sentence)) for sentence in df['sentence'].astype('str').tolist()]
        tokenized = [re.sub('[·•]', ' ', sentence) for sentence in tokenized]
    
    # Traditional Chinese
    elif lang_code == 'zh-TW':
        ws = WS("./ckiptagger_data")
        tokenized = [' '.ws(sentence) for sentence in df['sentence'].astype('str').tolist()]

    # append to the dataframe
    df['sentence_tok'] = tokenized
    df.drop(columns = 'sentence', axis = 1, inplace = True)

    return df

# Convert between simplified Chinese and traditional Chinese
def convert_chn(df, lang_code):
    if lang_code == 'zh-CN':
        converted = [chinese_converter.to_simplified(text) for text in df['sentence'].astype('str').tolist()]
        df['sentence'] = converted
    elif lang_code in ['yue', 'zh-HK', 'zh-TW', 'nan-TW']:
        converted = [chinese_converter.to_traditional(text) for text in df['sentence'].astype('str').tolist()]
        df['sentence'] = converted
    return df

def read_in_log(path):
    df = pd.read_csv(path, sep = '\t', quoting=csv.QUOTE_NONE, low_memory = False,
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
    return df

# Remap speakers and generate a speaker file
def remap_spkr(lang_dir, spkr_file_path, lang_code, is_cjk, output=True):
    clip_dir = os.path.join(lang_dir, 'clips') # Where all the clips are
    valid_log = os.path.join(lang_dir, 'validated.tsv') # where the validated utterance log of common voice is
    clip_dur_file = os.path.join(lang_dir, 'clip_durations.tsv') # where the clip duration file is

    validated = read_in_log(valid_log)
    validated['validation'] = 'validated'

    # Skip the clients whose data are deleted on Common Voice
    with open('speaker_skiplist.txt', 'r') as skip:
        speaker_skiplist = [line.strip() for line in skip.readlines()] # get the client ids that need to be skipped
    validated = validated[~validated['client_id'].isin(speaker_skiplist)]
    del speaker_skiplist

    # Get the clip durations
    clip_dur = pd.read_csv(clip_dur_file, sep = '\t', dtype = {'clip': 'str', 'duration[ms]': 'float64'})
    clip_dur.rename(columns = {'clip':'path', 'duration[ms]':'dur'}, inplace=True)
    clip_dur.set_index('path', inplace = True)

    # Append duration info to validated speaker file
    validated.set_index('path', inplace = True)
    validated = pd.concat([validated, clip_dur], axis = 1, join = 'inner')
    validated['dur'] = validated['dur']/1000
    validated.reset_index(inplace=True)
    del clip_dur

    # Create a column that shows if the clip is validated or not based on the votes
    conditions = [
        ((validated['validation'] == 'validated') & (validated['dur'] > 1)),
        (((validated['validation'] == 'validated') & (validated['dur'] <= 1)) |
         (len(str(validated['sentence'].str.strip())) == 0) |
         (validated['sentence'].isna()) |
         (validated['sentence'].str.contains('common_voice', regex = True)))
    ]
    choices = ["validated", "other"]
    validated["validation"] = np.select(conditions, choices)
    del conditions, choices

    # remap the speakers:
    validated['speaker_id'] = pd.factorize(validated['client_id'])[0] + 1
    validated['speaker_id'] = validated.speaker_id.astype('str')

    # subset the data to only validated recordings
    validated = validated[validated['validation'] == 'validated']
    validated.drop('validation', axis = 1, inplace = True)

    # Tokenize CJK texts
    if is_cjk:
        sentences = validated[['sentence_id', 'sentence']]
        unique_sentences = sentences.drop_duplicates()
        converted_sentence = convert_chn(unique_sentences, lang_code)
        tokenized_sentences = tok_cjk(converted_sentence, lang_code)
        validated = pd.merge(validated, tokenized_sentences, on= 'sentence_id', how = 'left')
        # Rarrange the columns so that the tokenized sentence is next to the original ones.
        cols = list(validated.columns)
        cols.remove('sentence_tok')
        target_index = cols.index('sentence_domain')
        cols.insert(target_index, 'sentence_tok')
        validated = validated[cols]
    
    # Normalize the apostrophe in Uzbek
    if lang_code == 'uz':
        # Replace the apostrophes after o and g with a simple '
        transcript = validated['sentence'].tolist()
        transcript = [re.sub(r"([oOgG])([ʼ‘’ʻ`'´])", r"\1ʻ", sentence) for sentence in transcript]
        transcript = [re.sub(r"([^\W\d_ogOG])([ʼ‘’ʻ`'´])", r"\1ʼ", sentence) for sentence in transcript]
        transcript = [re.sub(r"(-|•)", " ", sentence) for sentence in transcript]
        validated['sentence'] = transcript
        
    # save the speaker file
    if output:
        if os.path.exists(spkr_file_path):
            os.remove(spkr_file_path)
        validated.to_csv(spkr_file_path, sep='\t', index=False)

    # The file paths
    paths = validated['path'].tolist()
    validated['src_path'] = [os.path.join(clip_dir, path) for path in paths]
    validated['new_path'] = [os.path.join(lang_dir, 'validated', path) for path in paths]
    
    # If there are more than 32000 files, split them into groups and create paths in the subfolders
    if len(validated) > 32000:
        root = os.path.join(lang_dir, 'validated')
        num_groups = (len(validated) + 32000 - 1) // 32000
        validated['subfolder'] = ["subfolder_" + str(i+1).zfill(3) for i in range(num_groups) for _ in range(min(32000, len(validated) - i*32000))]
        validated['sub_path'] = [os.path.join(root, i, j) for i, j in zip(validated.subfolder, validated.path)]

    return validated

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

def move_and_create_tg(df, is_cjk):
    if is_cjk:
        for src_mp3_path, new_path, speaker, dur, transcript in zip(df.src_path, df.new_path, df.speaker_id, df.dur, df.sentence_tok):
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
    else:
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

# Define the function that removes Uzbek punctuations
def remove_uz_punct(text):
    # Step 1: Temporarily replace the specific cases with placeholders
    temp_replacement1 = re.sub(r"(oʻ|gʻ)", lambda m: m.group(0).replace("ʻ", "<T1>"), text)
    temp_replacement2 = re.sub(r"(\w)ʼ", lambda m: m.group(0).replace("ʼ", "<T2>"), temp_replacement1)
    
    # Step 2: Remove all remaining punctuation
    no_punctuation = re.sub(r"[^\w\s<>\d]", "", temp_replacement2)
    
    # Step 3: Reinsert the specific cases back with correct characters
    final_text = no_punctuation.replace("<T1>", "ʻ").replace("<T2>", "ʼ")
    return final_text

# Get words from transcripts:
def process_words(df, lang_code, is_cjk):
    # Read in the validated.tsv file and get the orthographical transcriptions of the utterances
    if is_cjk:
        words = df['sentence_tok'] # get the transcribed sentences
    else:
        words = df['sentence']
    words = words[words.notnull()]
    #print(words)

    # Remove the punctuations
    if lang_code == 'uz':
        words = pd.Series([remove_uz_punct(word) for word in words.tolist()])
    else:
        words = words.str.replace('[~|·|‧|⋯|⠀|︰|﹔|﹖|（|）|－|ㄧ|．|／|ａ|ｂ|，|。|！|～|￼|、|？|“|”|：|；|‘|’|…|《|》|【|】|「|」|=|•|\\\\|՜|։|՝|՛|।|›|‹|/|\(|\)|\[|\]|,|‚|።|፡|፣|.|،|!|?|+|\"|″|″|×|°|¡|“|⟨|⟩|„|→|‑|–|-|-|−|-|—|‒|۔|\$|ʻ|ʿ|ʾ|`|´|’|‘|«|»|;|؛|:|”|؟|&|\%|…|\t|\n| \' ]+', ' ', regex=True)

    # Remove the arabic punctuations and combining marks
    words = words.str.replace('[ء| ؓ| ؑ]+', ' ', regex=True)
    # Remove all numbers
    words = words.str.replace('[0-9]+', ' ', regex=True)
    #print(words)
    # Remove all remaining punctuations
    words = words.str.replace('[[:punct:]]+', ' ', regex=True)
    # Merge multiple continueing white spaces
    words = words.str.replace('[ ]+', ' ', regex=True)
    # To lower case
    words = words.str.lower()

    # Make it a list of the word types
    words = words.tolist()
    words = ' '.join(words)
    words = words.split(' ')
    words = sorted(set(words))
    words = [word for word in words if word.strip()]
    words = list(filter(None, words))

    # Filter out some text errors from Common Voice
    words = [re.sub('^mp3', '', word) for word in words]
    words = [word for word in words if 'common_voice' not in word]

    return words

##########################################################################################################
##########################################################################################################

# G2P

# Epitran
def remove_non_ipa_(string_list, ipa_symbols):
    result_list = []
    for string in string_list:
        # Find all IPA symbols and white spaces in the string using the regex pattern
        ipa_symbols_spaces = re.findall(ipa_symbols, string)
        
        # Concatenate the IPA symbols and white spaces to form a cleaned string
        cleaned_string = ''.join([group for group in ipa_symbols_spaces if group])
        
        # Append the cleaned string to the result list
        result_list.append(cleaned_string)
    
    return result_list

def epi_g2p(words, epi_code, dict_file_path):
    import epitran
    ipa_symbols = re.compile(r'([\u0020-\u007E\u00A0-\u00FF\u0100-\u017F\u0180-\u024F\u0250-\u02AF\u02B0-\u02FF\u0300-\u036F\u0370-\u03FF\u1AB0-\u1AFF\u1DC0-\u1DFF\u2000-\u206F\u2070-\u209F\u2190-\u21FF\u2C60-\u2C7F\uA700-\uA71F]+)|\s')

    if epi_code == 'cmn-Hans':
        epi = epitran.Epitran(epi_code, cedict_file = '/Users/miaozhang/Research/CorpusPhon/Scripts/vxc_pipeline/cedict_1_0_ts_utf-8_mdbg.txt')
    else:
        epi = epitran.Epitran(epi_code)

    lex_dict = {}
    for word in words:
        if epi_code == 'yue-Latn':
            jyutping = pycantonese.characters_to_jyutping(word)[0][1]
            if jyutping is None:
                phone = ''
            else:
                phone = epi.transliterate(jyutping)
                phone = re.sub(":", "ː", phone)
                # Attach the unreleased symbol to the coda stops
                phone = re.sub(r'(p|pʰ|t|tʰ|k|kʰ)($|p|t|t͡s|s|f|k|m|n|ŋ|l|j|w|h|ʔ)', lambda m: f"{m.group(1).replace('ʰ', '')}̚{m.group(2)}", phone) 
                #phone = re.sub(r'(t|tʰ)($|p|t|t͡s|s|f|k|m|n|ŋ|l|j|w|h|ʔ)', r't̚\2', phone)
                #phone = re.sub(r'(k|kʰ)($|p|t|t͡s|s|f|k|m|n|ŋ|l|j|w|h|ʔ)', r'k̚\2', phone)
                phone = ' '.join(ipa2tokens(phone))
                phone = re.sub(r'j (i|y)', r'\1', phone) # get rid of j before i or y in 
                phone = re.sub('w u', 'u', phone)  # get rid of w before u
                phone = re.sub(r'(k|kʰ)ʷ ', r'\1 ʷ', phone) # move the w onglide to group it with the rime instead of the consonant
        else:
            phone = epi.transliterate(word)
            phone = re.sub(":", "ː", phone)
            phone = ' '.join(ipa2tokens(phone))

        # Separate any identical ipa symbols repeated twice with a white space
        phone = re.sub(r'([\u0020-\u007E\u00A0-\u00FF\u0100-\u017F\u0180-\u024F\u0250-\u02AF\u02B0-\u02FF\u0300-\u036F\u0370-\u03FF])\1', r'\1 \1', phone)
        phone = re.sub(r'ˈ|ˌ', '', phone) # strip the stress markers

        if not re.sub(r'[^\w\s]', '', word): # if the word is an empty string, no phone output
            clean_phone = ''
        else:
            # Get rid of the non-IPAs from the output
            only_ipa = re.findall(ipa_symbols, phone)
            clean_phone = ' '.join(only_ipa)

        lex_dict[word] = clean_phone
        if phone != clean_phone:
            print(word + ': ' + phone + '\t' + clean_phone)

    # write to outfile
    with open(dict_file_path, 'w') as dict_file:
        for word, phone in sorted(lex_dict.items()):
            if phone.strip() != '': 
                dict_file.write(word + '\t' + phone + "\n")
    
# XPF
def xpf_g2p(xpf_translater_path, rule_file_path, verify_file_path, word_file_path, dict_file_path):
    g2p_cmd = ["python", xpf_translater_path, "-l", rule_file_path, "-c", verify_file_path, "-r", word_file_path] # XPF translating command that will be sent to subprocess.run() to execute.

    with open(dict_file_path,'w') as dict_file:
        subprocess.run(g2p_cmd, stdout = dict_file) # stdout = ... means to send the output to the file (so you have to open this file first as above)

    # This is to get rid of all the '@' in the lexicon (if there is any). @ means that XPF G2P failure
    with open(dict_file_path, "r") as dict_file:
        dict = dict_file.read().split("\n")

    with open(dict_file_path, 'w') as dict_file:
        for i in dict:
            i = re.sub(" ː", "ː", i)
            # Get rid of words that contain sounds XPF can't figure out
            if '@' not in i:
                dict_file.write(i + "\n")

# Charsiu
def chr_generate(words, code_chr):
    from transformers import T5ForConditionalGeneration, AutoTokenizer
    model = T5ForConditionalGeneration.from_pretrained('charsiu/g2p_multilingual_byT5_tiny_16_layers_100')
    tokenizer = AutoTokenizer.from_pretrained('google/byt5-small')

    def process_chunk(chunk):
        chr_words = [f'<{code_chr}>: '+i for i in chunk]
        out = tokenizer(chr_words, padding=True, add_special_tokens=False, return_tensors='pt')
        preds = model.generate(**out, num_beams=1, max_length=50)
        phones = tokenizer.batch_decode(preds.tolist(), skip_special_tokens=True)
        
        phones = [' '.join(ipa2tokens(phone)) for phone in phones]
        phones = [re.sub(':', 'ː', phone) for phone in phones]
        return phones

    # Split the 'words' list into chunks for processing
    chunk_size = 5000
    chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]

    # Process the chunks using ThreadPoolExecutor for parallel processing with threads
    with ThreadPoolExecutor(5) as executor:
        processed_phones = list(executor.map(process_chunk, chunks))

    # Combine the results from each chunk processing
    phones = [phone for chunk_result in processed_phones for phone in chunk_result]

    return phones

def chr_postproc(phones, code_chr):
    if code_chr == 'yue':
        # Change homosyllabic 't s' to 't͡s'
        pattern_ts = re.compile(r'(^|[˥˦˧˨˩]\s)t s')
        phones = [re.sub(pattern_ts, r'\1t͡s', phone) for phone in phones]

        # Change syllabic 'ŋ' to 'ŋ̩'
        pattern_ng_syll = re.compile(r'(^|[˥˦˧˨˩]\s)ŋ(\s[˥˦˧˨˩])')
        phones = [re.sub(pattern_ng_syll, r'\1ŋ̩\2', phone) for phone in phones]

        # Change labialzed 'k w' to 'k'
        pattern_kw = re.compile(r'(^|[˥˦˧˨˩]\s)(k|kʰ) w')
        phones = [re.sub(pattern_kw, r'\1\2ʷ', phone) for phone in phones]

        # Remove the onset /j, w/ before /i/ and /u/
        pattern_jiy = re.compile(r'(^|[˥˦˧˨˩]\s)j (i|y)')
        pattern_wu = re.compile(r'(^|[˥˦˧˨˩]\s)w u')
        phones = [re.sub(pattern_jiy, r'\1\2', phone) for phone in phones] 
        phones = [re.sub(pattern_wu, r'\1u', phone) for phone in phones]

        # Mark the syllabic final unreleased ptk
        pattern_ptk = r'[ptk]\s(?=˥|˦|˧|˨|˩)'
        phones = [re.sub(pattern_ptk, lambda x: x.group()[0]+'̚ ', phone) for phone in phones]
    
    elif code_chr == 'est':
        # Get rid of stress markers in Estonian
        phones = [re.sub(r' \^|ˈ|ˌ', '', phone) for phone in phones]

    # Put the tone markers to directly following the main vowel
    #pattern_tone_pos = re.compile(r'\s([mnŋptk])\s([˥˦˧˨˩]+)')
    #phones_with_tone = [re.sub(pattern_tone_pos, r' \2 \1', phone) for phone in phones]
    #phones_with_tone = [re.sub(r'(.)\s([˥˦˧˨˩]+)', r'\1\2', phone) for phone in phones_with_tone]
    # Strip away the tone markers
    phones = [re.sub(r'[˥˦˧˨˩]+', '', phone) for phone in phones]
    phones = [re.sub(r'\s+', ' ', phone) for phone in phones]

    return phones
 
def charsiu_g2p(words, code_chr, dict_file_path):
    phones = chr_generate(words, code_chr)
    phones = chr_postproc(phones, code_chr)
    # Save the output 
    transcript = []
    with open(dict_file_path, 'w') as dict_file:
        for word, phone in zip(words, phones):
            dict_file.write(word + '\t' + phone + "\n")
            transcript.append(word + '\t' + phone)

    return transcript

# Chinese g2p
def convert_cmn(chinese_text):
    py = pinyin(chinese_text, style=Style.TONE3)
    # Flatten the list and join words with spaces
    py = [item[0] for item in py]
    # Get each syllable
    ipa = [pinyin_to_ipa(item)[0] for item in py]
    ipa = [' '.join(sound) for sound in ipa]
    ipa = [re.sub('[˥˦˧˨˩]', '', sound) for sound in ipa]
    # Make onglides superscript and attach them to the following vowel
    ipa = [re.sub(r'(p|m|f|t|n|l|k|x|s|ʂ|ɻ|ʰ) w ', r'\1 ʷ', syll) for syll in ipa]
    ipa = [re.sub(r'(p|t|m|n|l|ɕ|ʰ) j ', r'\1 ʲ', syll) for syll in ipa]
    ipa = [re.sub(r'(n|l|ɕ|ʰ) ɥ ', r'\1 ᶣ', syll) for syll in ipa]
    ipa = [re.sub('a ŋ', 'ɑ ŋ', syll) for syll in ipa]
    ipa = ' '.join(ipa)
    
    transcript = chinese_text + '\t' + ipa
    
    return transcript

def cmn_g2p(words, dict_file_path):
    g2p_res = []    
    for word in words:
        transcript = convert_cmn(word)
        g2p_res.append(transcript)
    
    with open(dict_file_path, 'w') as dict:
        for line in g2p_res:
            dict.write(line + '\n')

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

def remove_non_chinese(text):
    # This pattern matches any character not in the specified Unicode blocks of Chinese characters
    pattern = r'[^\u4e00-\u9fff\u3400-\u4dbf]'
    # Remove non-Chinese characters
    clean_text = re.sub(pattern, '', text)
    return clean_text

# Filter Mongolian
def remove_non_mongolian(words):
    cyrillic_words = []
    for word in words:
        if re.match(r'^[а-яёүөӨҮА-ЯЁ\s]+$', word):  # Check if word contains only Cyrillic characters
            cyrillic_words.append(word)
    return cyrillic_words

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
# Regular expression for matching CJK characters


# Filter function to check if CJK characters are in a word
def contains_cjk(word):
    cjk_pattern = re.compile('[\u4e00-\u9fff\u3400-\u4dff\uac00-\ud7af\u3040-\u309f\u30a0-\u30ff]')
    return cjk_pattern.search(word) is not None
def remove_cjk(words):
    # Use list comprehension to filter out words containing CJK or non-Latin letters
    filtered_words = [word for word in words if not contains_cjk(word)]
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

# Filter out non-Cyrillic texts
def remove_non_cyrillic(words):
    cyrillic_words = []
    for word in words:
        if re.match(r'^[а-яёүөӨҮА-ЯЁ\s]+$', word):  # Check if the word contains only Cyrillic characters
            cyrillic_words.append(word)
    return cyrillic_words

# Remove latin letters
def remove_latin(word):
    remove_pattern = re.compile('[a-zA-Z]')
    return remove_pattern.sub('', word)


# Filter out unwanted words for Common Voice languages:
def remove_unwanted_words(word_list, lang_code, is_cjk, if_cyrl):
    if not is_cjk:
        # Filter out unwanted CJK words
        filtered_words = remove_cjk(word_list)
    else:
        # Otherwise remove the Latin letters
        filtered_words = [remove_latin(word) for word in word_list if remove_latin(word)]

    if if_cyrl == 1:
        filtered_words = remove_non_cyrillic(word_list)
        
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
    elif lang_code == 'sr': # filter Serbian
        filtered_words = remove_non_serbian(filtered_words)
    elif lang_code == 'mn': # filter Mongolian
        filtered_words = remove_non_mongolian(filtered_words)
    elif lang_code == 'zh-CN': # filter Chinese
        filtered_words = [remove_non_chinese(word) for word in filtered_words]

    filtered_words = [word for word in filtered_words if word.strip() != '']
    return filtered_words