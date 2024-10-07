import argparse
import json
import os
from typing import Literal

from halo import Halo

from bibles import (
    get_bb_audio,
    get_bb_text,
    get_chapter_info,
    get_dbl_audio,
    get_dbl_text,
    get_timings,
)
from constants import bible_chapters, mms_languages, translations
from model import load_model
from timestamp_types import ChapterInfo, ChapterText

parser = argparse.ArgumentParser()

parser.add_argument(
    "-o",
    "--output",
    help="The path to a folder to write chapter json files to.",
    required=True,
)
parser.add_argument(
    "-l",
    "--language",
    help="The mms language id of the bible.",
    required=True,
    type=str,
)


def get_audio(chapter_info: ChapterInfo, source: Literal["bb", "dbl"], b_id: str):
    spinner = Halo()
    if os.path.exists(chapter_info["paths"]["audio"]):
        spinner.info(f"({chapter_info['chapter_id']}) Audio already exists. Skipping.")
        return

    if source == "bb":
        get_bb_audio(
            b_id, chapter_info["chapter_id"], output=chapter_info["paths"]["audio"]
        )
    elif source == "dbl":
        get_dbl_audio(
            b_id, chapter_info["chapter_id"], output=chapter_info["paths"]["audio"]
        )
    else:
        print("Invalid source")
        exit(0)


def get_text(chapter_info: ChapterInfo, source: Literal["bb", "dbl"], b_id: str):
    spinner = Halo()

    if (
        os.path.exists(chapter_info["paths"]["text"])
        and len(
            json.load(open(chapter_info["paths"]["text"], encoding="utf-8"))["verses"]
        )
        > 0
    ):
        spinner.info(f"({chapter_info['chapter_id']}) Text already exists. Skipping.")
        return

    # Start with an empty chapter text object that we will fill in.
    chapter_text: ChapterText = {
        "translationId": b_id,
        "bookName": "",
        "chapterId": chapter_info["chapter_id"],
        "reference": "",
        "verses": [],
    }

    if source == "bb":
        get_bb_text(
            b_id,
            chapter_info["chapter_id"],
            chapter_text,
            output=chapter_info["paths"]["text"],
        )
    elif source == "dbl":
        get_dbl_text(
            b_id,
            chapter_info["chapter_id"],
            chapter_text,
            output=chapter_info["paths"]["text"],
        )
    else:
        print("Invalid source")
        exit(0)


def main():
    args = parser.parse_args()
    language = args.language
    output = args.output
    os.makedirs(output, exist_ok=True)

    if language is not None:
        # Check if language is valid.
        language_match = next(
            (item for item in mms_languages if item["iso"] == language), None
        )

        if language_match is None or not language_match["align"]:
            print("Provided language is not supported by mms.")
            exit(0)

    b_match = next(
        (item for item in translations if item["languageId"] == language), None
    )

    if b_match is None:
        print("Translation not added to translations.json.")
        exit(0)

    model, dictionary = load_model()

    for chapter_id in bible_chapters:
        chapter_info = get_chapter_info(chapter_id, output)

        b_ids = b_match["nt"] if chapter_info["testament"] == "nt" else b_match["ot"]
        if b_ids is None:
            continue

        os.makedirs(chapter_info["paths"]["book"], exist_ok=True)

        get_audio(chapter_info, b_match["source"], b_ids["audio"])

        get_text(chapter_info, b_match["source"], b_ids["text"])

        get_timings(language, chapter_info, model, dictionary)


main()
