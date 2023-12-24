#!/usr/bin/python
# -*- coding: utf-8 -*-

#  format_lexicons
#  
#
#  Created by Eleanor Chodroff on Nov 14 2021.

import sys, codecs, re

file = 'basque.txt'
new_dict = codecs.open('basque_lexicon.txt', 'w', "utf-8")


f = codecs.open(file, 'r', "utf-8")
for line in f:
    col = line.split(',')
    orth = col[0]
    segs = col[1]
    phon = ' '.join(segs)
    phon = re.sub('@ ', '', phon)
    phon = re.sub(' ̪', '̪', phon)
    phon = re.sub(' ̻', '̻', phon)
    phon = re.sub(' ̺', '̺', phon)
    phon = re.sub('d z','dz', phon)
    phon = re.sub('d ʒ','dʒ', phon)
    phon = re.sub('t s̺','ts̺', phon)
    phon = re.sub('t s̻', 'ts̻', phon)
    phon = re.sub('t ʃ','tʃ', phon)
    new_dict.write(orth + '\t' + phon)