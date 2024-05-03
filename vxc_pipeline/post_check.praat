# This is a script that allows you to check the alignments for some sound files.

# Created by Miao Zhang, 30.04.2024

csv_file$ = chooseReadFile$: "Choose the csv file"

table = Read Table from comma-separated file: csv_file$
n_rows = Get number of rows

for i from 1 to n_rows
	selectObject: table
	snd$ = Get value: i, "sound"
	tg$ = Get value: i, "textgrid"
	
	if fileReadable (snd$) and fileReadable (tg$) 
		snd = Read from file: snd$
		tg = Read from file: tg$
		
		selectObject: snd
		plusObject: tg
		View & Edit
		pause
		removeObject: snd, tg
	else
		writeInfoLine: "This file: " + snd$ + " is not openable."
		pause
	endif

endfor

removeObject: table
