import argparse
import json
import os

from halo import Halo

from model import load_model
from timestamp_types import File
from utils import align_matches, match_files

mms_languages = json.load(open("data/mms_languages.json"))

parser = argparse.ArgumentParser()
parser.add_argument(
    "-i",
    "--input",
    help="The path to a folder containing audio and text files.",
    required=True,
)
parser.add_argument(
    "-o",
    "--output",
    help="The path to a json file to write the timestamps to.",
    required=True,
)
parser.add_argument(
    "-s",
    "--separator",
    help=(
        "The location to timestamp within a text file. Options are `lineBreak`, "
        "`leftBracket` ([), or `downArrow` (⬇️)."
    ),
    default="lineBreak",
)
parser.add_argument(
    "-l",
    "--language",
    help=(
        "The language of the text and audio files. If one isn't provided, the app "
        "will automatically detect the language using MMS's lid api."
    ),
    default=None,
    type=str,
)
parser.add_argument(
    "-m",
    "--max-silence-padding-ms",
    help=(
        "The maximum amount of silence padding (in ms) to offset the start and end "
        "timestamps of each text span. Default is -1 (equally distribute silence). "
        "0 will remove all silence. 500 (for example) will add up to 500ms of "
        "silence to the start and end of each text span."
    ),
    default=-1,
    type=int,
)


def main():
    args = parser.parse_args()
    folder = args.input
    output = args.output
    separator = args.separator
    language = args.language
    max_silence_padding_ms = args.max_silence_padding_ms

    if language is not None:
        # Check if language is valid.
        language_match = next(
            (item for item in mms_languages if item["iso"] == language), None
        )

        if language_match is None or not language_match["align"]:
            print(f"Invalid language detected.")
            exit(0)

    model, dictionary = load_model()

    files: list[File] = []

    for dirpath, _, filenames in os.walk(folder):
        for file_name in filenames:
            file_path = os.path.join(dirpath, file_name)
            absolute_path = os.path.abspath(file_path)
            files.append((file_name, absolute_path))

    matched_files = match_files(files)
    spinner = Halo(text=f"Matching files in {folder}...").start()
    for match in matched_files:
        if match[0] is None:
            spinner.fail(f"Can't find match for {match[1]}.")
        elif match[1] is None:
            spinner.fail(f"Can't find match for {match[0]}.")

    spinner.succeed(f"Finished matching files in {folder}.")

    for match in matched_files:
        if match[0] is None or match[1] is None:
            continue
    timestamps = align_matches(
        folder, language, separator, matched_files, model, dictionary, max_silence_padding_ms
    )
    json.dump(timestamps, open(output, "w"))


main()
