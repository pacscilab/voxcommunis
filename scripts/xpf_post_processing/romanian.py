#!/usr/bin/python
# -*- coding: utf-8 -*-

#
import sys, codecs, re

file = 'romanian.txt'
new_dict = codecs.open('romanian_lexicon.txt', 'w', "utf-8")

f = codecs.open(file, 'r', "utf-8")
for line in f:
    line = line.split(',')
    orth_orig = line[0]
    orth = orth_orig.lower()
    segs = line[1]
    if 'ü' in orth:
    	segs = re.sub('@', 'u', segs)    
    if 'y' in orth:
    	segs = re.sub('@', 'i', segs)    
    if 'w' in orth:
    	segs = re.sub('@', 'u', segs)   
    phon = ' '.join(segs)
    phon = re.sub(' ̪', '̪', phon)
    phon = re.sub('t ʃ', 'tʃ', phon)
    phon = re.sub('d ʒ', 'dʒ', phon)
    new_dict.write(orth_orig + '\t' + phon)
