# getFormantsCommonVoice_highlow.praat
# Specify high (5 formants @ 5500Hz) or low (5 formants @ 5000Hz) formant ranges for 1 language's dataset
# Get formants 1--4 at predefined points in the vowel: quartiles AND midpoint window (10ms before and after midpoint)
# Get information about the file, vowel, and duration
# Uses IPA
# All decimals are rounded to 4 places (using fixed$)
# Based on original script by Eleanor Chodroff: getFormantsWilderness.praat
# Modified by Emily P. Ahn
# 6 December 2021

# ###################
masterdir$ = "/Users/eahn/work/typ/data/comvoi/"
lang$ = "kyrgyz"
# var totalFormants: range [2-4] only
totalFormants = 4
# var highLow: {high,low} only
highLow$ = "low"
# highLow$ = "high"
# ###################
sep$ = ","
tg_dir$ = masterdir$ + lang$ + "/aligned_validated/"
wav_dir$ = masterdir$ + lang$ + "/prep_validated/"
# write formant file to same lang-specific dir that contains {prep,aligned}_validated/
outfile$ = masterdir$ + lang$ + "/" + lang$ + "_formants_" + highLow$ + string$(totalFormants) + ".csv"
@createHeader

Create Strings as file list: "files", tg_dir$ + "*.TextGrid"
nFiles = Get number of strings
for i from 1 to nFiles
	@processFile
endfor

# assumes totalFormants is between 2 and 4
procedure createHeader
	appendFile: outfile$, "file", sep$, "vowel", sep$, "prec", sep$, "foll", sep$
	appendFile: outfile$, "start", sep$, "end", sep$, "dur", sep$
	appendFile: outfile$, "f1_start", sep$, "f1_q1", sep$, "f1_mid", sep$, "f1_q3", sep$, "f1_end", sep$
	appendFile: outfile$, "f1_mp1", sep$, "f1_mp2", sep$
	appendFile: outfile$, "f2_start", sep$, "f2_q1", sep$, "f2_mid", sep$, "f2_q3", sep$, "f2_end", sep$
	appendFile: outfile$, "f2_mp1", sep$, "f2_mp2"
	if totalFormants > 2
		appendFile: outfile$, sep$, "f3_start", sep$, "f3_q1", sep$, "f3_mid", sep$, "f3_q3", sep$, "f3_end", sep$
		appendFile: outfile$, "f3_mp1", sep$, "f3_mp2"
	endif
	if totalFormants > 3
		appendFile: outfile$, sep$, "f4_start", sep$, "f4_q1", sep$, "f4_mid", sep$, "f4_q3", sep$, "f4_end", sep$
		appendFile: outfile$, "f4_mp1", sep$, "f4_mp2"
	endif
	appendFile: outfile$, newline$
endproc


procedure processFile
	selectObject: "Strings files"
	filename$ = Get string: i
	basename$ = filename$ - ".TextGrid"
	Read from file: tg_dir$ + basename$ + ".TextGrid"
	Read from file: wav_dir$ + basename$ + ".wav"

	# convert wav files to formant objects
	# use default female settings if "high", male if "low"
	# [OLD: TRACKING] only track if total # of formants is 2 (Track setting often fails with 3 or 4)
	if highLow$ == "high"
		# To Formant (burg): 0, 4, 4200, 0.025, 50
		To Formant (burg): 0, 5, 5500, 0.025, 50
		# if totalFormants = 2
		# 	nocheck Track: 2, 550, 1650, 2750, 3850, 4950, 1.0, 1.0, 1.0
		# endif
	elsif highLow$ == "low"
		# To Formant (burg): 0, 4, 4000, 0.025, 50
		To Formant (burg): 0, 5, 5000, 0.025, 50
		# if totalFormants = 2
		# 	nocheck Track: 2, 500, 1500, 2500, 3500, 4500, 1.0, 1.0, 1.0
		# endif
	endif

	# loop through TextGrid to find vowels
	selectObject: "TextGrid " + basename$

	# EPA: add info because there are several tiers. Only want phone tier
	nTiers = Get number of tiers
	for tier to nTiers
		tierName$ = Get tier name: tier
		if endsWith(tierName$, "phones")

			nInt = Get number of intervals: tier
			for j from 1 to nInt
				selectObject: "TextGrid " + basename$
				label$ = Get label of interval: tier, j
				# updated set of vowels below, IPA format (not XSAMPA)
				if index_regex(label$, "^[əʉæɶɑɛɪɔʊʏɒaeiouyɨøɜɐɤɵœɯɘɞʌä]")
					@getLabels
					@getTime
					for form from 1 to totalFormants
						@getFormants: form
					endfor
				endif
			endfor
		endif
	endfor

	# pauseScript: "done one file"
	# do some clean up
	select all
	minusObject: "Strings files"
	Remove
endproc

procedure getLabels
	if j > 1
		prec$ = Get label of interval: tier, j-1
	else
		prec$ = "NA"
	endif
	if j < nInt
		foll$ = Get label of interval: tier, j+1
	else
		foll$ = "NA"
	endif
	appendFile: outfile$, basename$, sep$, label$, sep$, prec$, sep$, foll$, sep$
endproc

procedure getTime
	start = Get start time of interval: tier, j
	end = Get end time of interval: tier, j
	dur = end - start
	# round values to 4 decimals at most
	appendFile: outfile$, number(fixed$(start, 4)), sep$, number(fixed$(end, 4)), sep$, number(fixed$(dur, 4)), sep$
endproc

procedure getFormants: formantNum
	selectObject: "Formant " + basename$

	# round all values to 4 decimals at most
	# get formants at each quartile (including start and end)
	for f from 0 to 4
		f_time4 = Get value at time: formantNum, start + f*(dur/4), "hertz", "Linear"
		appendFile: outfile$, fixed$(f_time4, 4), sep$
	endfor

	# get formants at 2 additional points: 10ms before midpoint & 10ms after midpoint
	f_time_mp1 = Get value at time: formantNum, start + (dur/2) - 0.01, "hertz", "Linear"
	f_time_mp2 = Get value at time: formantNum, start + (dur/2) + 0.01, "hertz", "Linear"
	appendFile: outfile$, fixed$(f_time_mp1, 4), sep$
	if formantNum = totalFormants
		appendFile: outfile$, fixed$(f_time_mp2, 4), newline$
	else
		appendFile: outfile$, fixed$(f_time_mp2, 4), sep$
	endif

endproc
