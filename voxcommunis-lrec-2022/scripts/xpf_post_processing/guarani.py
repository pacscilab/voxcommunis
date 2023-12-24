#!/usr/bin/python
# -*- coding: utf-8 -*-

#  format_lexicons
#  
#
#  Created by Eleanor Chodroff on Nov 7 2021.

import sys, codecs, re

file = 'guarani.txt'
new_dict = codecs.open('guarani_lexicon.txt', 'w', "utf-8")


f = codecs.open(file, 'r', "utf-8")
for line in f:
    col = line.split(',')
    orth = col[0]
    segs = col[1]	
    phon = ' '.join(segs)
    phon = re.sub('ⁿ ','ⁿ', phon)
    phon = re.sub('ᵐ ', 'ᵐ', phon)
    phon = re.sub('ᵑ ','ᵑ', phon)
    phon = re.sub('d ʒ','dʒ', phon)
    new_dict.write(orth + '\t' + phon)