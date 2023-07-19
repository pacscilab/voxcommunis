import sys
import csv

# written by Emily P. Ahn for VoxCommunis
# 2021
# remap Common Voice client_id to a simpler speaker_id (in order of appearance)
# add speaker_id as column to TSV (i.e. validated.tsv)
# write out that file to save it
# To run:
#	python q_remap_comvoi_spkrs.py {tsv_infile} {tsv_outfile}
#	ex: py src/q_remap_comvoi_spkrs.py data/comvoi/uzbek/docs/validated.tsv data/comvoi/uzbek/docs/validated_spkr.tsv


cv_in_tsvfile = sys.argv[1]
cv_out_tsvfile = sys.argv[2]


with open(cv_in_tsvfile, newline='') as csvfile:
	reader = csv.DictReader(csvfile, delimiter='\t')
	client_set = set([row['client_id'] for row in reader])

	# assign speaker_id #
	spkr_map = {}
	i = 0
	for client_name in client_set:
		spkr_map[client_name] = str(i).zfill(5)
		i += 1

with open(cv_in_tsvfile, newline='') as csvfile:
	reader = csv.DictReader(csvfile, delimiter='\t')

	with open(cv_out_tsvfile, 'w', newline='') as csv_writer:
		fieldnames = reader.fieldnames
		fieldnames.extend(['speaker_id', 'new_utt'])
		writer = csv.DictWriter(csv_writer, delimiter='\t', fieldnames=fieldnames)
		writer.writeheader()

		for row in reader:
			spkr_digits = spkr_map[row['client_id']]
			new_row = row
			new_row['speaker_id'] = spkr_digits
			new_row['new_utt'] = "{}_{}".format(spkr_digits, row['path'].replace('.mp3', ''))
			writer.writerow(new_row)
