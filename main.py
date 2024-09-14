import argparse
import json
import os

from halo import Halo

from model import load_model
from timestamp_types import File
from utils import align_matches, match_files

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
    help="The location to timestamp within a text file.",
    default="lineBreak",
)


def main():
    args = parser.parse_args()
    folder = args.input
    output = args.output
    separator = args.separator

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
    timestamps = align_matches(folder, separator, matched_files, model, dictionary)
    json.dump(timestamps, open(output, "w"))


main()
