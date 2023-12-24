#!/usr/bin/python
# -*- coding: utf-8 -*-

#  format_lexicons
#  
#
#  Created by Eleanor Chodroff on Nov 7 2021.

import sys, codecs, re

file = 'bashkir2.txt'
new_dict = codecs.open('bashkir_lexicon_extra.txt', 'w', "utf-8")


f = codecs.open(file, 'r', "utf-8")
for line in f:
    col = line.split(',')
    orth = col[0]
    segs = col[1]
    phon = ' '.join(segs)
    if 'ц' in orth:
    	phon = re.sub('t s', 'ts', phon)
    if 'Ц' in orth:
        phon = re.sub('t s', 'ts', phon)
    if 'ч' in orth:
    	phon = re.sub('t ʃ', 'tʃ', phon)
    if 'Ч' in orth:
        phon = re.sub('t ʃ', 'tʃ', phon)
    if '—' in orth:
    	phon = re.sub('@', '', phon)
    if 'й' in orth:
    	phon = re.sub('@', 'i', phon)
    new_dict.write(orth + '\t' + phon)