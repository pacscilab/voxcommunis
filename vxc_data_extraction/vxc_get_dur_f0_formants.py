import pandas as pd
pd.options.mode.copy_on_write = True
import os, logging, argparse, time
from praatio import textgrid
import parselmouth as psm
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

# List of IPA vowel symbols
target_vowels = [
    'i', 'y', 'ɪ', 'ʏ', 'ɐ', 'a', 'ɑ', 'ɒ', 'ɯ', 'u',  'ʊ'
]

# Helper function to check if a label contains any IPA vowel symbol
def contains_vowel(label):
    return any(vowel in label for vowel in target_vowels)

# Define a function to identify monophthongs
def is_monophthong(label):
    # Remove stress markers at the beginning if they exist
    if label.startswith("'") or label.startswith("ˈ"):
        label = label[1:]  # Remove the stress marker for further checks

    # Check if it's a monophthong without stress or with the long vowel marker
    return len(label) == 1 or (len(label) == 2 and (label[1] == 'ː' or label[1] == ':'))

# Helper function to process a single TextGrid file
def process_textgrid_file(lang_code, tg_file, tg_dir, snd_dir):
    results = []
    tg_path = os.path.join(tg_dir, tg_file)
    tg_name = os.path.basename(tg_file)
    file_id, _ = os.path.splitext(tg_name)
    snd_name = file_id + '.mp3'
    snd_file = os.path.join(snd_dir, snd_name)

    failed_intervals = 0
    processed_intervals = 0
    total_duration = 0
    total_intervals = 0
    non_spn_intervals = []

    if not os.path.exists(snd_file):
        logging.warning(f"Sound file {snd_file} does not exist. Skipping.")
        return results, failed_intervals, processed_intervals

    try:
        tg = textgrid.openTextgrid(tg_path, includeEmptyIntervals=True)
        word_tier = tg.getTier(tg.tierNames[0]) # Get the word tier
        seg_tier = tg.getTier(tg.tierNames[1]) # Get the segment tier

        # Get the total duration and number of non-'spn' intervals
        utterance_start = min(start for start, stop, label in seg_tier.entries if label)
        utterance_end = max(stop for start, stop, label in seg_tier.entries if label)
        utterance_duration = utterance_end - utterance_start

        # Get the total duration and number of non-'spn' intervals
        for start, stop, label in seg_tier.entries:
            if label and label != 'spn':
                intv_dur = stop - start
                total_duration += intv_dur
                total_intervals += 1
                non_spn_intervals.append((start, stop, label))

        # Read the sound file
        snd = psm.Sound(snd_file)

        # Get the pitch object
        pitch = snd.to_pitch_ac(time_step=None, pitch_floor=75.0, pitch_ceiling=500.0)
        f0s = pitch.selected_array["frequency"]
        times = pitch.xs()

        # Get the formant object
        formants = snd.to_formant_burg(time_step = None, max_number_of_formants = 5)

        for i in range(len(seg_tier.entries)):
            start, stop, label = seg_tier.entries[i]
            if contains_vowel(label) and is_monophthong(label) and label:
                intv_dur = round((stop - start) * 1000)
                if intv_dur >= 30:

                    prev_label = seg_tier.entries[i - 1][2] if i > 0 else 'NA'
                    next_label = seg_tier.entries[i + 1][2] if i < len(seg_tier.entries) - 1 else 'NA'

                    word_info = None
                    for word_idx, (word_start, word_stop, word_label) in enumerate(word_tier.entries):
                        if word_start <= start and word_stop >= stop:
                            word_info = (word_label, round((word_stop - word_start) * 1000), word_idx)
                            break
                    
                    if not word_info:
                        logging.warning(f"No matching word found for segment {label} at interval {i}.")
                        continue

                    word_label, word_dur, _ = word_info
                    # Determine the position within the utterance
                    relative_start_percentage = (start - utterance_start) / utterance_duration
                    if relative_start_percentage <= 0.25:
                        intv_pos = 'front_25'
                    elif relative_start_percentage <= 0.75:
                        intv_pos = 'mid_50'
                    else:
                        intv_pos = 'last_25'

                    mid_start = start + (stop - start) * 0.45
                    mid_stop = stop - (stop - start) * 0.45
                    mid_indices = np.where(np.logical_and(times >= mid_start, times <= mid_stop))
                    target_f0s = f0s[mid_indices]
                    valid_f0s = target_f0s[target_f0s > 0]

                    f1_vals = []
                    f2_vals = []
                    for time in times[mid_indices]:
                        f1_value = formants.get_value_at_time(1, time)
                        f2_value = formants.get_value_at_time(2, time)
                        if f1_value is not None and not np.isnan(f1_value):
                            f1_vals.append(f1_value)
                        if f2_value is not None and not np.isnan(f2_value):
                            f2_vals.append(f2_value)

                    if valid_f0s.size > 0 and f1_vals and f2_vals:
                        mean_f0 = np.nan if valid_f0s.size == 0 else np.mean(valid_f0s)
                        mean_f1 = 'NA' if not f1_vals else np.nanmean(f1_vals)
                        mean_f2 = 'NA' if not f2_vals else np.nanmean(f2_vals)
                        if mean_f0 is not np.nan and not np.isnan(mean_f0) and 75 <= mean_f0 <= 500:
                            f0 = round(mean_f0)
                            f1 = 'NA' if mean_f1 == 'NA' or np.isnan(mean_f1) else round(mean_f1)
                            f2 = 'NA' if mean_f2 == 'NA' or np.isnan(mean_f2) else round(mean_f2)
                            results.append([lang_code, file_id, prev_label, label, i, next_label, intv_dur, f0, f1, f2, 
                                            word_label, word_dur, round(total_duration*1000), total_intervals, intv_pos])
                            processed_intervals += 1
                    else:
                        failed_intervals += 1
                else:
                    failed_intervals += 1

    except Exception as e:
        logging.error(f"Error processing {tg_file}: {e}")

    return results, failed_intervals, processed_intervals

def parse_args():
    parser = argparse.ArgumentParser(description="Process TextGrid files for speech analysis.")
    parser.add_argument("commonvoice_dir", type=str, help="Path to the CommonVoice directory")
    parser.add_argument("lang_code", type=str, help="Language code")
    parser.add_argument("ver_num", type=str, help="Version number")
    parser.add_argument("output_dir", type=str, help="Directory to save the output CSV file")
    return parser.parse_args()

def main(commonvoice_dir, lang_code, ver_num, output_dir):
    # Record the start time
    start_time = time.time()

    # Define paths
    lang_dir = os.path.join(commonvoice_dir, f'{lang_code}_v{ver_num}')
    tg_dir = os.path.join(lang_dir, 'output')
    snd_dir = os.path.join(lang_dir, 'validated')
    output_csv = os.path.join(output_dir, f'{lang_code}_v{ver_num}_results.csv')

    results = []
    total_failed_intervals = 0
    total_processed_intervals = 0

    # Using ProcessPoolExecutor for parallel processing
    max_workers = min(10, os.cpu_count() or 1)  # Adapt according to your CPU
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_textgrid_file, lang_code, tg_file.name, tg_dir, snd_dir): tg_file.name
            for tg_file in os.scandir(tg_dir) if tg_file.is_file() and tg_file.name.endswith('.TextGrid')
        }

        for future in as_completed(futures):
            try:
                res, failed_intervals, processed_intervals = future.result()
                if res:
                    results.extend(res)
                total_failed_intervals += failed_intervals
                total_processed_intervals += processed_intervals
            except Exception as e:
                logging.error(f"Error in future result: {e}")

    # Save results to CSV
    df = pd.DataFrame(results, columns=['lang_code', 'file_id', 'prev_seg', 'seg', 'seg_intv', 'next_seg', 'seg_dur', 'F0', 'F1', 'F2',
                                        'word', 'word_dur', 'utt_dur', 'n_phone', 'utt_pos'])
    if not df.empty:
        df.to_csv(output_csv, index=False)
        print(f"Results saved to {output_csv}")
    else:
        print("No valid results to save")

    # Report the number of processed and failed intervals
    print(f"Number of vowel intervals successfully processed: {total_processed_intervals}")
    print(f"Number of vowel intervals that failed to yield an F0 value: {total_failed_intervals}")

    # Record the end time
    end_time = time.time()
    runtime = end_time - start_time
    # Convert the elapsed time to hours, minutes, and seconds
    hours, rem = divmod(runtime, 3600)
    minutes, seconds = divmod(rem, 60)

    # Print the runtime
    print(f"Runtime: {int(hours):02}:{int(minutes):02}:{seconds:.2f}")

if __name__ == "__main__":
    args = parse_args()
    main(args.commonvoice_dir, args.lang_code, args.ver_num, args.output_dir)
