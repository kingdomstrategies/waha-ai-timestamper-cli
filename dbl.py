import argparse
import json
import os
import urllib.request
from typing import Any, TypedDict

from dotenv import load_dotenv
from halo import Halo

from model import load_model
from timestamp_types import File
from utils import align_matches

load_dotenv()

bible_chapters = json.load(open("bible_chapters.json"))

mms_languages = json.load(open("mms_languages.json"))

parser = argparse.ArgumentParser()
parser.add_argument(
    "-t",
    "--text-id",
    help="The id for the dbl text translation to use.",
    required=True,
)
parser.add_argument(
    "-a",
    "--audio-id",
    help="The id for the dbl audio translation to use.",
    required=True,
)
parser.add_argument(
    "-o",
    "--output",
    help="The path to a folder to write json files to.",
    required=True,
)
parser.add_argument(
    "-l",
    "--language",
    help="The language of the text and audio files. If one isn't provided, the app will automatically detect the language using MMS's lid api.",
    default=None,
    type=str,
)


class Verse(TypedDict):
    verse_id: str
    text: str


def add_dbl_text(verses: list[Verse], item: Any):
    """API.Bible-specific function to add text to the chapter object."""

    if "attrs" in item and "verseId" in item["attrs"]:
        verse_id: str = item["attrs"]["verseId"]

        existing_element: Verse | None = None

        for verse in verses:
            if verse["verse_id"] == verse_id:
                existing_element = verse

        if existing_element is not None:
            existing_element["text"] += item["text"]
        else:
            verses.append(
                {
                    "verse_id": verse_id,
                    "text": item["text"],
                }
            )


def get_chapter(
    folder: str, text_translation_id: str, audio_translation_id: str, chapter_id: str
) -> tuple[File, File]:
    spinner = Halo("Fetching text...").start()

    if not os.path.exists(f"{folder}/{chapter_id}.json"):

        req = urllib.request.Request(
            "https://api.scripture.api.bible/v1"
            f"/bibles/{text_translation_id}"
            f"/chapters/{chapter_id}"
            "?content-type=json&include-notes=false&include-titles=true"
            "&include-chapter-numbers=false&include-verse-numbers=true"
            "&include-verse-spans=false"
        )
        req.add_header("api-key", os.getenv("API_BIBLE_KEY", ""))
        resp = urllib.request.urlopen(req).read()
        json_response = json.loads(resp.decode("utf-8"))

        # TEXT

        verses: list[Verse] = []

        # Iterate through reponse and add all text to an object.
        for verse_chunk in json_response["data"]["content"]:
            for item1 in verse_chunk["items"]:
                if "items" in item1:
                    for item2 in item1["items"]:
                        if "items" in item2:
                            for item3 in item2["items"]:
                                add_dbl_text(verses, item3)
                        else:
                            add_dbl_text(verses, item2)
                else:
                    add_dbl_text(verses, item1)

        json.dump(verses, open(f"{folder}/{chapter_id}.json", "w"))

    # AUDIO

    spinner.text = "Fetching audio..."

    if not os.path.exists(f"{folder}/{chapter_id}.mp3"):
        fetch_url = (
            "https://api.scripture.api.bible/v1"
            f"/audio-bibles/{audio_translation_id}"
            f"/chapters/{chapter_id}"
        )

        req = urllib.request.Request(fetch_url)
        req.add_header("api-key", os.getenv("API_BIBLE_KEY", ""))
        resp = urllib.request.urlopen(req).read()
        json_response = json.loads(resp.decode("utf-8"))

        urllib.request.urlretrieve(
            json_response["data"]["resourceUrl"],
            f"{folder}/{chapter_id}.mp3",
        )

    spinner.succeed(f"Finished fetching {chapter_id}.")
    return (
        f"{chapter_id}.mp3",
        f"{folder}/{chapter_id}.mp3",
    ), (f"{chapter_id}.json", f"{folder}/{chapter_id}.json")


def main():
    args = parser.parse_args()
    folder = f"/tmp/{args.text_id}"
    os.makedirs(folder, exist_ok=True)
    output = args.output
    os.makedirs(output, exist_ok=True)
    language = args.language

    if language is not None:
        # Check if language is valid.
        language_match = next(
            (item for item in mms_languages if item["iso"] == language), None
        )

        if language_match is None or not language_match["align"]:
            print(f"Invalid language detected.")
            exit(0)

    model, dictionary = load_model()

    matched_files = []

    for chapter in bible_chapters:
        if chapter != "GEN.2":
            continue
        matched_files.append(get_chapter(folder, args.text_id, args.audio_id, chapter))

    timestamps = align_matches(
        folder,
        language,
        "",
        matched_files,
        model,
        dictionary,
    )
    for chapter in timestamps:
        json.dump(chapter, open(f"{output}/{chapter['text_file']}", "w"))


main()
