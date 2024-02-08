# VoxCommunis Corpus
 
This repository contains the code for generating files in the VoxCommunis Corpus, hosted at https://osf.io/t957v/ (DOI: 10.17605/OSF.IO/T957V). In particular, it contains the code for the processing pipeline of VoxCommunis Corpus. These codes can be found in two folders in the repo: `vxc_lang_code_processing` and `vxc_pipeline`. 

## The scripts

The `vxc_lang_code_processing` folder contains the code to generate the file to log the language name/code (as in [Common Voice](https://commonvoice.mozilla.org/en/datasets), [XPF corpus](https://www.urielcohenpriva.com/xpf.html), and [Epitran](https://pypi.org/project/epitran/)), and the info about numbers of hours of recordings for each language from [Common Voice](https://commonvoice.mozilla.org/en/datasets). The `vxc_lang_code_processing/vxc_tracking.csv` logs the updates of pronunciation lexicons, speaker IDs, and the acoustic models for each language.

The processing pipeline notebook script `vxc_processing_pipeline.ipynb` can be found in the `vxc_pipeline` folder. This script requires four other scripts to run properly:

- `vxc_naming_schema.csv`: to setup the file names of the pipeline output.
- `vxc_remap_spkrs.py`: to remap the client ID from Common Voice to speaker IDs of VoxCommunis.
- `createTextGridsWav.praat`: to create .wav and .TextGrid files for the validated recordings from Common Voice.
- `epi_run.py` or `xpf_translator04.py`: to create a pronunciation lexicon for VoxCommunis based on the Common Voice transcripts. The former runs `Epitran` while the latter runs `XPF` translator.
 
## The output

The output of the processing will contain:

- pronunciation lexicons
- speaker IDs
- acoustic models
- aligned TextGrids
- vowel formant measurements
- segment duration measurements
- vowel f0 measurements

It also contains the code and data used in the original paper on the VoxCommunis Corpus in voxcommunis-lrec-2022/. This paper can be found at https://aclanthology.org/2022.lrec-1.566/ and cited as:

Ahn, Emily, and Chodroff, Eleanor. (2022). VoxCommunis: A corpus for cross-linguistic phonetic analysis. Proceedings of the 13th Conference on Language Resources and Evaluation Conference (LREC 2022).

@inproceedings{ahn2022voxcommunis,
  title={Vox{C}ommunis: A corpus for cross-linguistic phonetic analysis},
  author={Ahn, Emily and Chodroff, Eleanor},
  booktitle={Proceedings of the Thirteenth Language Resources and Evaluation Conference},
  pages={5286--5294},
  year={2022}
}
