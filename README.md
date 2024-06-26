# VoxCommunis Corpus
 
This repository contains the code for generating files in the VoxCommunis Corpus, hosted at [VoxCommunis Corpus](https://osf.io/t957v/) (DOI: 10.17605/OSF.IO/T957V). In particular, it contains the code for the processing pipeline of VoxCommunis Corpus.

## The scripts

The `vxc_lang_code_processing` folder contains the script `vxc_process_lang_codes.ipynb` to generate the file `VoxCommunis_Info.csv` which logs the language name/code (as used in [Common Voice](https://commonvoice.mozilla.org/en/datasets), [XPF corpus](https://cohenpr-xpf.github.io/XPF/), and [Epitran](https://pypi.org/project/epitran/)), and numbers of hours of recordings for each language from [Common Voice](https://commonvoice.mozilla.org/en/datasets). The `VoxCommunis_tracking.csv` logs the updates of pronunciation lexicons, speaker IDs, and the acoustic models for each language, which will be manually updated. To run `vxc_process_lang_codes.ipynb`, five files are needed:

- `cv_languages.py`: contains the language name and code from Common Voice.
- `cv_release_stats.py`: contains the release information of each language in Common Voice.
- `epi_langs-list.csv`: contains the languages and their processing codes in `Epitran`.
- `iso-639-3.tab`: contains the ISO639-1 and ISO639-3 codes for languages.
- `xpf_langs-list.tsv`: contains the languages and their codes in XPF corpus.

The `vxc_pipeline` contains the script to run the data processing pipeline `vxc_processing_pipeline.ipynb`. This script also requires *five* other scripts to run properly:

- `vxc_processing.py`: contains all the functions the pipeline is using.
- `vxc_naming_schema.csv`: to set up the file names of the pipeline output.
- `epi_run.py` or `xpf_translator04.py`: to create a pronunciation lexicon for VoxCommunis based on the Common Voice transcripts. The former runs `Epitran` while the latter runs `XPF` translator.
- `speaker_skiplist.txt`: contains client ids for speakers whose data have been deleted from Common Voice.
- `mfa_align.sh`: the bash script to loop through the subfolders to align data when the corpus is too large.

If you want to use the G2P models from Epitran, you will need to download and install the package first (`pip install epitran`). If you want to use XPF, you will need to download the [XPF data](https://github.com/CohenPr-XPF/XPF/tree/master/Data) and save it on your computer. If you want to use Charsiu G2P, please follow the instruction on its [GitHub repo](https://github.com/lingjzhu/CharsiuG2P). [MFA](https://mfa-models.readthedocs.io/en/latest/index.html) also provides G2P models and lexicons.
 
## The output

The output of the processing will contain:

- pronunciation lexicons
- speaker IDs
- acoustic models
- aligned TextGrids
- vowel formant measurements
- segment duration measurements
- vowel f0 measurements

However, these output files will not be included in this GitHub repository. Please find them on the OSF repository of [VoxCommunis Corpus](https://osf.io/t957v/).

## Ahn, Emily, and Chodroff, Eleanor. (2022)

This repository also contains the code and data used in the original paper on the VoxCommunis Corpus in `voxcommunis-lrec-2022/`. This paper can be found at https://aclanthology.org/2022.lrec-1.566/ and cited as:

Ahn, Emily, and Chodroff, Eleanor. (2022). VoxCommunis: A corpus for cross-linguistic phonetic analysis. Proceedings of the 13th Conference on Language Resources and Evaluation Conference (LREC 2022).

@inproceedings{ahn2022voxcommunis,
  title={Vox{C}ommunis: A corpus for cross-linguistic phonetic analysis},
  author={Ahn, Emily and Chodroff, Eleanor},
  booktitle={Proceedings of the Thirteenth Language Resources and Evaluation Conference},
  pages={5286--5294},
  year={2022}
}
