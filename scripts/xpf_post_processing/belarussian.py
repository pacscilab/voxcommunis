#!/usr/bin/python
# -*- coding: utf-8 -*-

#  format_lexicons
#  
#
#  Created by Eleanor Chodroff on Nov 7 2021.

import sys, codecs, re

file = 'belarussian_xpf.txt'
new_dict = codecs.open('belarussian_lexicon.txt', 'w', "utf-8")


f = codecs.open(file, 'r', "utf-8")
for line in f:
    col = line.split(',')
    orth = col[0]
    segs = col[1]
    phon = ' '.join(segs)
    phon = re.sub(' ː','ː', phon)
    phon = re.sub(' ʲ', 'ʲ', phon)
    phon = re.sub('d z','dz', phon)
    phon = re.sub('d ʒ','dʒ', phon)
    phon = re.sub('t s','ts', phon)
    phon = re.sub('t ʃ', 'tʃ', phon)
    phon = re.sub('@', 'i', phon)
    new_dict.write(orth + '\t' + phon)
