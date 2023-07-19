#!/usr/bin/python
# -*- coding: utf-8 -*-

#  format_lexicons
#  
#
#  Created by Eleanor Chodroff on Nov 7 2021.

import sys, codecs, re

file = 'tatar.txt'
new_dict = codecs.open('tatar_lexicon.txt', 'w', "utf-8")


f = codecs.open(file, 'r', "utf-8")
for line in f:
    col = line.split(',')
    orth = col[0]
    segs = col[1]
    segs = re.sub('@', 'ts', segs)
    phon = ' '.join(segs)
    new_dict.write(orth + '\t' + phon)