import re, csv, os, shutil, epitran, subprocess
import pandas as pd
import numpy as np
from praatio import textgrid
from pathlib import Path

# Japanese tokenizer
from fugashi import Tagger
import pykakasi
# Korean tokenizer
#from konlpy.tag import Okt
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
# Taiwanese Southern Min
import taibun
# Korean G2P
from g2pk2 import G2p
# Thai Tokenizer
from pythainlp import word_tokenize

# Tokenize IPA
from lingpy import ipa2tokens

##################################################################################################
##################################################################################################

# The function to tokenize CJK languages:
# Convert between simplified Chinese and traditional Chinese
def convert_chn(df, lang_code):
    if lang_code in ['zh-CH', 'yue', 'zh-HK', 'zh-TW', 'nan-tw']:
        if lang_code == 'zh-CN':
            converted = [chinese_converter.to_simplified(text) for text in df['sentence'].astype('str').tolist()]
            df['sentence'] = converted
        elif lang_code in ['yue', 'zh-HK', 'zh-TW', 'nan-tw']:
            converted = [chinese_converter.to_traditional(text) for text in df['sentence'].astype('str').tolist()]
            df['sentence'] = converted
    return df

def tok_cjk(df, lang_code):
    sentences = df['sentence'].astype('str').tolist()

    if lang_code == 'ja':
        wakati = Tagger('-Owakati')    
        tokenized = [re.sub(r'[,。、「」\[\]\%\(\)（）・？!]+', ' ', text) for text in sentences]
        tokenized = [re.sub(r'[a-zA-Z\d\s\W]+', ' ', text) for text in tokenized]
        tokenized = [wakati.parse(sentence) for sentence in tokenized]
        # Japanse text post processing: putting the phonological words together as much as possible
        tokenized = [re.sub(r'([っッ]) ', r'\1', text) for text in tokenized]
        tokenized = [re.sub(r'([んン]) ', r'\1', text) for text in tokenized]
        tokenized = [re.sub(r'[ ]*(ん)[ ]*', r'\1', text) for text in tokenized]
        tokenized = [re.sub(r' し (て|た)', r'し\1', text) for text in tokenized]
        jpn_part = re.compile(r' (た|だ|が|の|を|に|へ|と|から|より|で|のに|や|し|やら|か|なり|だの|ばかり|まで|だけ|ほど|くらい|ぐらい|など|なり|やら|がてら|なぞ|なんぞ|かり|ずつ|のみ|きり|は|も|こそ|でも|しか|さえ|ば|ても|でも|けど|けれど|けれども|のに|ので|から|し|して|て|なり|ながら|ては|ても|たり|つつ|ところで|まま|ものの|か|な|とも|ぞ|ぜ|かい|よ|ね|さ|やら|ものか|わ|もの|かしら|ってば|って|さ|よ|ね|な|なあ|でき|的な|的に|的だ|的で|ください)($| )')
        tokenized = [re.sub(jpn_part, r'\1\2', text) for text in tokenized]
        tokenized = [re.sub(r' (派|所|達|語|的|町|県|市|町|区|村|州|学|て|方|機)', r'\1', text) for text in tokenized]
        tokenized = [re.sub(r'(何|一|二|三|四|五|六|七|八|九|十) (年|月|日|回|階)', r'\1\2', text) for text in tokenized]
        tokenized = [re.sub(r' (新) ', r' \1', text) for text in tokenized]

    # Cantonese
    elif lang_code in ['yue', 'zh-HK']:
        tokenized = [' '.join(pycantonese.segment(sentence)) for sentence in sentences]
    
    # Simplified Chinese
    elif lang_code == 'zh-CN':
        seg = pkuseg.pkuseg()
        tokenized = [' '.join(seg.cut(sentence)) for sentence in sentences]
        tokenized = [re.sub('[·•]', ' ', sentence) for sentence in tokenized]
    
    # Traditional Chinese
    elif lang_code == 'zh-TW':
        ws = WS("./ckiptagger_data")
        tokenized = ws(sentences)
        tokenized = [' '.join(item) for item in tokenized]
    
    elif lang_code == 'nan-tw':
        t = taibun.Tokeniser()
        sentences = df['sentence'].str.replace(r'[^\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', '', regex = True).tolist()
        tokenized = [' '.join(t.tokenise(sent)) for sent in sentences]

    elif lang_code == 'th':
        tokenized = [' '.join(word_tokenize(sent, keep_whitespace=False)) for sent in sentences]
    
    elif lang_code == 'ko':
        ko_g2p = G2p()
        tokenized = [ko_g2p(text) for text in df['sentence'].astype('str').tolist()]

    # append to the dataframe
    df['sentence_tok'] = tokenized
    df.drop(columns = 'sentence', axis = 1, inplace = True)

    return df


def read_in_log(path):
    df = pd.read_csv(path, sep = '\t', quoting=csv.QUOTE_NONE, low_memory = False,
                          dtype = {
                              'client_id': 'str',
                              'path': 'str',
                              'sentence_id': 'str',
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
def remap_cjk_spkr(lang_dir, spkr_file_path, lang_code, output=True):
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

    # Word tokenization for CJKs
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

##################################################################################################
##################################################################################################

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

def move_and_create_cjk_tg(df):
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


##################################################################################################
##################################################################################################


# G2P

# Epitran
ipa_symbols = re.compile(r'[\u0020-\u007E\u00A0-\u00FF\u0100-\u017F\u0180-\u024F\u0250-\u02AF\u02B0-\u02FF\u0300-\u036F\u0370-\u03FF\u1AB0-\u1AFF\u1DC0-\u1DFF\u2000-\u206F\u2070-\u209F\u2190-\u21FF\u2C60-\u2C7F\uA700-\uA71F]+|\s')

def filter_ipa_symbols(input_string):
    filtered_string = ''.join(char for char in input_string if ipa_symbols.match(char))

    return filtered_string if len(filtered_string) == len(input_string) else ''

def epi_cjk_g2p(words, epi_code, dict_file_path):
    epi = epitran.Epitran(epi_code)

    if epi_code == 'jpn-Ktkn': # G2P Japanese
        kks = pykakasi.kakasi()
        katn = [kks.convert(word) for word in words]
        trans = []
        for item, word in zip(katn, words):
            #print(item)
            reading = []
            for ind, i in enumerate(item):
                if i['orig'] in ['いう', '言う']:
                    i['kana'] = 'ユウ'
                if ind == len(item) - 1:
                    if i['orig'] == 'は':
                        i['kana'] = 'ワ'
                    elif i['orig'] == 'へ':
                        i['kana'] = 'エ'
                #reading = ''.join(reading)
            reading = ''.join(reading)
            #print(''.join(reading))
            pron = epi.trans_list(reading)
            pron = ' '.join(pron)
            pron = re.sub(r'(\S+) \1', r'\1ː', pron)
            hv_devoice_pattern = re.compile(r"(p|t|k|kʲ|s|ç|ɕ)([ː]?) (i|ɯ) (p|t|k|kʲ|s|ç|ɕ)([ː]?)")
            while True:
                pron, count = re.subn(hv_devoice_pattern, r"\1\2 \3̥ \4\5", pron)
                if count == 0:  # No more replacements possible
                    break

            pron = re.sub('o ɯ', 'oː', pron)
            pron = re.sub(r'(ː̃ )', r'\1 ', pron)
            pron = re.sub('ɰ', 'w', pron)
            pron = re.sub('ɖ', 'ɾ', pron)
            clean_pron = filter_ipa_symbols(pron)
            if pron != clean_pron:
                print(word + '\t"' + pron + '"\t"' + clean_pron + '"')
            if clean_pron != '':
                entry = word + '\t' + clean_pron
                trans.append(entry)

        with open(dict_file_path, 'w') as f:
            for i in trans:
                f.write(i + '\n')

    else:
        lex_dict = {}
        for word in words:
            if epi_code == 'yue-Latn': # G2P Cantonese
                jyutping = pycantonese.characters_to_jyutping(word)[0][1]
                if jyutping is None:
                    phone = ''
                else:
                    phone = epi.transliterate(jyutping)
                    phone = re.sub(":", "ː", phone)
                    # Attach the unreleased symbol to the coda stops
                    phone = re.sub(r'(p|pʰ|t|tʰ|k|kʰ)($|p|t|t͡s|s|f|k|m|n|ŋ|l|j|w|h|ʔ)', lambda m: f"{m.group(1).replace('ʰ', '')}̚{m.group(2)}", phone) 
                    phone = ' '.join(ipa2tokens(phone))
                    phone = re.sub(r'j (i|y)', r'\1', phone) # get rid of j before i or y 
                    phone = re.sub('w u', 'u', phone)  # get rid of w before u
                    phone = re.sub(r'(k|kʰ)ʷ ', r'\1 ʷ', phone) # move the w onglide to group it with the rime instead of the consonant
            elif epi_code == 'kor-Hang':
                phone = epi.transliterate(word)
                phone = ' '.join(ipa2tokens(phone, merge_vowels = False))
                phone = re.sub('d ʑ', 'd͡ʑ', phone)
            else: # Any other langauges
                phone = epi.transliterate(word)  
                phone = ' '.join(ipa2tokens(phone))

            phone = re.sub(":", "ː", phone)
            # Separate any identical ipa symbols repeated twice with a white space
            phone = re.sub(r'([\u0020-\u007E\u00A0-\u00FF\u0100-\u017F\u0180-\u024F\u0250-\u02AF\u02B0-\u02FF\u0300-\u036F\u0370-\u03FF])\1', r'\1 \1', phone)
            
            # Estonian super long vowels
            if epi_code == 'est-Latn':
                phone = re.sub('ː ː', 'ːː', phone) # String the super long symbol back
            phone = re.sub(r'ˈ|ˌ', '', phone) # strip the stress markers

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

# Taiwanese Minnan G2P

def nan_g2p(words, dict_file_path):
    c = taibun.Converter(system='IPA', format='strip')
    g2p_res = []
    ipa = [c.get(word).lower() for word in words]
    ipa = [i.split(' ') for i in ipa]
    for word in ipa:
        trans = [re.sub(r'(t|d)(z|ʑ|s|ɕ)', r'\1͡\2', i) for i in word]
        trans = [re.sub('chı', 't͡ɕi', i) for i in trans]
        trans = [' '.join(ipa2tokens(i)) for i in trans]
        trans = ' '.join(trans)
        g2p_res.append(trans)
        #print(trans)

    with open(dict_file_path, 'w') as f:
        for word, phone in zip(words, g2p_res):
            phone = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', '', phone)
            if phone != '':
                f.write(word+'\t'+phone+'\n')

# Korean G2P
def kor_xpf(words, xpf_translater_path, rule_file_path, verify_file_path, word_file_path, inter_file_path, dict_file_path):
    from g2pk import G2p # type: ignore
    kor_g2p = G2p()
    # Figure out Korean phonology hidden in their orthography
    kor_conv = [kor_g2p(word) for word in words]
    kor_conv_words = inter_file_path
    # Save the interim conversion to a file
    with open(kor_conv_words, 'w') as word_file:
        for word in kor_conv:
            word_file.write(word + "\n")
            
    # XPF convert Korean to IPA using the interim file
    g2p_cmd = ["python", xpf_translater_path, "-l", rule_file_path, "-c", verify_file_path, "-r", kor_conv_words] # XPF translating command that will be sent to subprocess.run() to execute.

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
    
    # Append the converted IPA transcription to the original word list file.
    kor_ipa = []
    with open(dict_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            parts = line.split('\t')
            if len(parts) == 2:
                _, string2 = parts
                kor_ipa.append(string2)
    with open(word_file_path, 'r') as f:
        kor_words = f.readlines()
        kor_words = [word.strip() for word in kor_words]
    with open(dict_file_path, 'w') as f:
        for word, ipa in zip(kor_words, kor_ipa):
            f.write(word+'\t'+ipa+'\n')