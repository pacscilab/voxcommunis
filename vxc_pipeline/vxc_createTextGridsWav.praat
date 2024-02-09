form 
	sentence: "Dir", "/Users/miaozhang/Research/CommonVoice/sorbian_upper_v15"
	sentence: "Dir_folder", "/Users/miaozhang/Research/CommonVoice/sorbian_upper_v15/validated"
	sentence: "Tsv_file", "/Users/miaozhang/Research/CommonVoice/sorbian_upper_v15/validated_spkr.tsv"
endform


Read Table from tab-separated file: tsv_file$
Rename: "files"

nRows = Get number of rows
for i from 1 to nRows
	selectObject: "Table files"
	file$ = Get value: i, "path"
	orig_utt$ = file$ - ".mp3"
	new_utt$ = Get value: i, "new_utt"
	sentence$ = Get value: i, "sentence"
	# replace any dash with a white space:
	sentence$ = replace$(sentence$, "-", " ", 0)
	sentence$ = replace_regex$(sentence$, "[ ]+", " ", 0)
	speakerID$ = Get value: i, "speaker_id"

	# READ FROM MP3 AND SAVE TO WAV
	Read from file: dir$ + "/clips/" + file$
	nowarn Save as WAV file: dir_folder$ + "/" + new_utt$ + ".wav"

	dur = Get total duration
	# create TextGrid with sentence and save, make sure the tier name is the speaker ID
	To TextGrid: speakerID$, "" 
	Insert boundary: 1, 0.05
	Insert boundary: 1, dur - 0.05
	Set interval text: 1, 2, sentence$
	Save as text file: dir_folder$ + "/" + new_utt$ + ".TextGrid"

	select all
	minusObject: "Table files"
	Remove
endfor

