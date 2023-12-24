import epitran
import csv
import re
import sys

# written by Emily P. Ahn for VoxCommunis
# 2021

# To run:
#	python q_epi_wordlist.py {txt_infile} {lex_outfile} {epi_code}
#	ex: py src/q_epi_wordlist.py data/comvoi/polish_oovs_found.txt data/comvoi/polish_oovs_epi.txt pol-Latn

cv_txtfile = sys.argv[1]
lex_outfile = sys.argv[2]
epi_code = sys.argv[3]  # ex. 'kaz-Cyrl'

epi = epitran.Epitran(epi_code)

lex_dict = {}

with open(cv_txtfile, newline='') as f:

	for word in f.readlines():
		word = word.strip()
		# import pdb; pdb.set_trace()

		phones = epi.trans_list(word)  # default: ligatures=False
	
		# strip punct temporarily to see if word is ONLY punct (skip)

		if not re.sub("[^\w\s]", "", word):
 			lex_dict[word] = ''
		
		clean_phones = [phone for phone in phones if not bool(re.match('[^\w\s]', phone))]
		lex_dict[word] = clean_phones
		if phones != clean_phones:
			print(phones, '\n', clean_phones)

# write to outfile
with open(lex_outfile, 'w') as w:
	for word, phones in sorted(lex_dict.items()):
		# separate phones with white space
		# phone_seq = ' '.join(list(phones.strip()))
		phone_seq = ' '.join(phones)
		w.write('{}\t{}\n'.format(word, phone_seq))
