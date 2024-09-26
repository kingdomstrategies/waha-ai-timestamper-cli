import argparse
import json
import os

from halo import Halo

from bibles import get_bb_audio, get_bb_text, get_chapter_info, get_timings
from constants import bb_translations, bible_chapters, mms_languages
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


def get_audio(chapter_info: ChapterInfo, bb_id: str):
    spinner = Halo()
    if os.path.exists(chapter_info["paths"]["audio"]):
        spinner.info(f"({chapter_info['chapter_id']}) Audio already exists. Skipping.")
        return

    get_bb_audio(
        bb_id, chapter_info["chapter_id"], output=chapter_info["paths"]["audio"]
    )


def get_text(
    chapter_info: ChapterInfo,
    bb_id: str,
):
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
        "translationId": bb_id,
        "bookName": "",
        "chapterId": chapter_info["chapter_id"],
        "reference": "",
        "verses": [],
    }

    get_bb_text(
        bb_id,
        chapter_info["chapter_id"],
        chapter_text,
        output=chapter_info["paths"]["text"],
    )


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
    # find element in bb_languages array where language_id is equal to language
    bb_match = next(
        (item for item in bb_translations if item["languageId"] == language), None
    )

    if bb_match is None:
        print("Translation not added to bb_translations.json.")
        exit(0)

    model, dictionary = load_model()

    for chapter_id in bible_chapters:
        chapter_info = get_chapter_info(chapter_id, output)

        bb_ids = bb_match["nt"] if chapter_info["testament"] == "nt" else bb_match["ot"]
        if bb_ids is None:
            continue

        os.makedirs(chapter_info["paths"]["book"], exist_ok=True)

        get_audio(chapter_info, bb_ids["audio"])

        get_text(chapter_info, bb_ids["text"])

        get_timings(language, chapter_info, model, dictionary)


main()
