#!/usr/bin/python
# -*- coding: utf-8 -*-

#  format_lexicons
#  
#
#  Created by Eleanor Chodroff on Nov 10 2021.

import sys, codecs, re

file = 'vietnamese.txt'
new_dict = codecs.open('vietnamese_lexicon.txt', 'w', "utf-8")


f = codecs.open(file, 'r', "utf-8")
for line in f:
    col = line.split(',')
    orth = col[0]
    segs = col[1]
    phon = ' '.join(segs)
    phon = re.sub(' ː', 'ː', phon)
    phon = re.sub(' ˩', '˩', phon)
    phon = re.sub(' ˨', '˨', phon)
    phon = re.sub(' ˧', '˧', phon)
    phon = re.sub(' ˥', '˥', phon)
    phon = re.sub(' ˀ', 'ˀ', phon)
    phon = re.sub(' ʰ', 'ʰ', phon)
    phon = re.sub(' ̪', '̪', phon)
    phon = re.sub('t ɕ','tɕ', phon)
    phon = re.sub('ɯ ɤ','ɯɤ', phon)
    phon = re.sub('u o','uo', phon)
    phon = re.sub('i e','ie', phon)
    new_dict.write(orth + '\t' + phon)