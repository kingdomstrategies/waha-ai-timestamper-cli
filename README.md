# TimestampAudio CLI by Waha

![TimestampAudio.com Logo](./logo.png "TimestampAudio.com Logo")

[TimeStampAudio](https://timestampaudio.com) generates timing data from any audio and corresponding text file combination, in the over [1,100 languages](https://dl.fbaipublicfiles.com/mms/misc/language_coverage_mms.html) supported by [Meta's MMS ASR model](https://ai.meta.com/blog/multilingual-model-speech-recognition/), outputting the results in JSON.


## Requirements:

We have successfully run this tool on both MacOS and Linux laptops with only CPUs by simply running the command below.

However, the MMS model works most efficiently with a CUDA enabled GPU. 

While an Mac M1 Pro could timestamp a 10 minute audio file in about 2.5 minutes, that same file could be timestamped in _just a few seconds_ when processed with a GPU.


## Installation:

Installation is fairly straight-forward. Simply:

1. Clone the repository.
2. Install the required Python libraries:

```sh
pip install -r requirement
```
3. You're ready to go!


## Usage:

To start timestamping, the first step is to organize your files.

The script will process an entire directory, expecting to find pairs of files with matching names, in `.mp3` and `.txt` format. So `GEN.1.mp3` and `GEN.1.txt`


When run on a directory, every pair of files with matching names will be processed.


```
$ tree .
.
├── GEN.1.mp3
├── GEN.1.txt
├── GEN.2.mp3
├── GEN.2.txt
├── GEN.3.mp3
├── GEN.3.txt
├── GEN.4.mp3
├── GEN.4.txt
├── GEN.5.mp3
└── GEN.5.txt
```


\
You can run the CLI tool with the following arguments:

```sh
python cli_tool.py -i <input_folder> -o <output_file>.json [-s <separator>] [-l <language>]
```

The script will output a single JSON file with an object for each audio-text file-pair.


### Arguments

- `-i, --input` (required): The path to a folder containing audio and text files.
- `-o, --output` (required): The path to a JSON file to write the timestamps to.
- `-s, --separator` (optional): The location to timestamp within a text file. Options are `lineBreak`, `leftBracket` ([), or `downArrow` (⬇️). Default is `lineBreak`.
- `-l, --language` (optional): The language of the text and audio files. If not provided, the app will automatically detect the language using MMS's lid API.

## Example

```sh
python cli_tool.py -i ./data -o timestamps.json -s lineBreak -l en
```
