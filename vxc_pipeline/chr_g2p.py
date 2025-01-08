import argparse, re, itertools

# Multithreading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load the pretrained model
from transformers import T5ForConditionalGeneration, AutoTokenizer
model = T5ForConditionalGeneration.from_pretrained('charsiu/g2p_multilingual_byT5_tiny_16_layers_100')
tokenizer = AutoTokenizer.from_pretrained('google/byt5-small')

# Tokenize IPA
from lingpy import ipa2tokens

# Define all IPA plus white space
ipa_symbols = re.compile(r'[\u0020-\u007E\u00A0-\u00FF\u0100-\u017F\u0180-\u024F\u0250-\u02AF\u02B0-\u02FF\u0300-\u036F\u0370-\u03FF\u1AB0-\u1AFF\u1DC0-\u1DFF\u2000-\u206F\u2070-\u209F\u2190-\u21FF\u2C60-\u2C7F\uA700-\uA71F]+|\s')

########################################################################################################################
########################################################################################################################

# Charsiu
def chr_generate(wordlist, code_chr):
        chr_words = [f'<{code_chr}>: '+i for i in wordlist]
        out = tokenizer(chr_words, padding=True, add_special_tokens=False, return_tensors='pt')
        preds = model.generate(**out, num_beams=1, max_length=50)
        phones = tokenizer.batch_decode(preds.tolist(), skip_special_tokens=True)
        
        phones = [' '.join(ipa2tokens(phone)) for phone in phones if phone.strip() != '']
        phones = [re.sub(':', 'ː', phone) for phone in phones]
        phones = [re.sub('ː([aɐɑæɶeɛəɜɞiɪyɨʉøɵœoɔuʊɯɤʌ]ː)', 'ː \1', phone) for phone in phones]
        return phones

def chr_postproc(phones, code_chr):
    # Separate identical IPAs
    phones = [re.sub(r'([\u0020-\u007E\u00A0-\u00FF\u0100-\u017F\u0180-\u024F\u0250-\u02AF\u02B0-\u02FF\u0300-\u036F\u0370-\u03FF])\1', r'\1 \1', phone) for phone in phones]

    only_ipa = [re.findall(ipa_symbols, phone) for phone in phones]
    phones = [' '.join(phone) for phone in only_ipa]
    # Strip away the tone stress markers
    phones = [re.sub(r'[˥˦˧˨˩]+|ˈ|ˌ', '', phone) for phone in phones]
    # Get rid of extra white spaces
    phones = [re.sub(r'\s+', ' ', phone) for phone in phones]
    
    return phones

def charsiu_g2p(words, code_chr):
    phones = chr_generate(words, code_chr)
    phones = chr_postproc(phones, code_chr)
    return phones
 
def charsiu_g2p_parallel(words, code_chr):
    with ThreadPoolExecutor(8) as executor:
        futures = [executor.submit(charsiu_g2p, [word], code_chr) for word in words]
        phones_list = [future.result() for future in as_completed(futures)]
    phones_list = [(word, phone) for word, phones in zip(words, phones_list) for phone in phones]
    
    return phones_list

def main():
    parser = argparse.ArgumentParser(description='Perform Charsiu g2p conversion with post-processing')
    parser.add_argument('word_file', type=str, help='Input word file')
    parser.add_argument('code_chr', type=str, help='Code for processing')
    parser.add_argument('dict_file_path', type=str, help='Path to the output dictionary file')
    args = parser.parse_args()

    word_file = args.word_file
    code_chr = args.code_chr
    dict_file_path = args.dict_file_path

    with open(word_file, 'r') as file:
        lines = file.readlines()
        words = [line.strip() for line in lines]

    phones_list = charsiu_g2p_parallel(words, code_chr)

    with open(dict_file_path, 'w') as dict_file:
        for word, phone in phones_list:
            dict_file.write(f"{word}\t{phone}\n")

if __name__ == "__main__":
    main()

