#!/usr/bin/python
# -*- coding: utf-8 -*-

#  format_lexicons
#  
#
#  Created by Eleanor Chodroff on Nov 7 2021.

import sys, codecs, re

file = 'ukrainian.txt'
new_dict = codecs.open('ukrainian_lexicon.txt', 'w', "utf-8")


f = codecs.open(file, 'r', "utf-8")
for line in f:
    col = line.split(',')
    orth = col[0]
    segs = col[1]
    #print(segs)
    phon = ' '.join(segs)
    phon = re.sub('@ ', 'i ', phon)
    phon = re.sub('t ʃ', 'tʃ', phon)
    phon = re.sub('d ʒ','dʒ', phon)
    phon = re.sub(' ʲ','ʲ', phon)
    new_dict.write(orth + '\t' + phon)