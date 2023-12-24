dir$ = "/Users/eleanor/Documents/asturian/"
filetype$ = "validated"
tsv_file$ = "validated_spkr.tsv"
dir_filetype$ = dir$ + "prep_" + filetype$ + "/"
Read Table from tab-separated file: dir$ + tsv_file$
Rename: "files"

nRows = Get number of rows
for i from 1 to nRows
	selectObject: "Table files"
	file$ = Get value: i, "path"
	orig_utt$ = file$ - ".mp3"
	new_utt$ = Get value: i, "new_utt"
	sentence$ = Get value: i, "sentence"
	speakerID$ = Get value: i, "speaker_id"

	# convert to wav and save
	# TOGGLE BETWEEN A AND B BELOW

	# A) READ FROM OLD WAV (DELETE) AND SAVE TO NEW WAV
	#Read from file: dir_filetype$ + orig_utt$ + ".wav"
	#nowarn Save as WAV file: dir_filetype$ + new_utt$ + ".wav"
	#deleteFile: dir_filetype$ + orig_utt$ + ".wav"
	#deleteFile: dir_filetype$ + orig_utt$ + ".TextGrid"
	#Read from file: dir_filetype$ + new_utt$ + ".wav"

	# B) READ FROM MP3 AND SAVE TO WAV
	Read from file: dir$ + "clips/" + file$
	nowarn Save as WAV file: dir_filetype$ + new_utt$ + ".wav"

	dur = Get total duration
	# create TextGrid with sentence and save
	To TextGrid: speakerID$, ""
	Insert boundary: 1, 0.05
	Insert boundary: 1, dur - 0.05
	Set interval text: 1, 2, sentence$
	Save as text file: dir_filetype$ + new_utt$ + ".TextGrid"

	select all
	minusObject: "Table files"
	Remove
endfor

