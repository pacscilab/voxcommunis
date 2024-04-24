import epitran, jamo, csv, re, sys, g2pk

# written by Emily P. Ahn for VoxCommunis
# 2021

# slightly modified by Miao Zhang
# skip outputting the empty strings to the lexicon file
# change the ":" in output to the IPA long vowel symbol "ː"
# added code to process Mandarin Chinese
# 2024/04/17

# To run:
#	python q_epi_wordlist.py {txt_infile} {lex_outfile} {epi_code}
#	ex: py src/q_epi_wordlist.py data/comvoi/polish_oovs_found.txt data/comvoi/polish_oovs_epi.txt pol-Latn

cv_txtfile = sys.argv[1]
lex_outfile = sys.argv[2]
epi_code = sys.argv[3]  # ex. 'kaz-Cyrl'

if epi_code == 'cmn-Hans':
	epi = epitran.Epitran(epi_code, cedict_file = 'cedict_1_0_ts_utf08_mdbg.txt')
else:
	epi = epitran.Epitran(epi_code)

lex_dict = {}

with open(cv_txtfile, newline='') as f:

	for word in f.readlines():
		word = word.strip()
		# import pdb; pdb.set_trace()

		phones = epi.trans_list(word)  # default: ligatures=False
		phones = [re.sub(":", "ː", phone) for phone in phones]
	
		# strip punct temporarily to see if word is ONLY punct (skip)

		if not re.sub("[^\w\s]", "", word):
 			lex_dict[word] = ''
		
		clean_phones = [phone for phone in phones if not bool(re.match('[^\w\s]', phone))]
		lex_dict[word] = clean_phones
		if phones != clean_phones:
			print(word, ': ', phones, '\t', clean_phones, '\n')

# write to outfile
with open(lex_outfile, 'w') as w:
	for word, phones in sorted(lex_dict.items()):
		# separate phones with white space
		# phone_seq = ' '.join(list(phones.strip()))
		phone_seq = ' '.join(phones)
		phone_seq = re.sub(" ː", "ː", phone_seq)
		if len(phone_seq.strip()) != 0: 
			w.write(f'{word}\t{phone_seq}\n')
