import argparse
import json
import os
import urllib.request

from dotenv import load_dotenv
from halo import Halo

from model import load_model
from timestamp_types import File, Verse
from utils import align_matches

load_dotenv()

bible_chapters = json.load(open("bible_chapters.json", encoding="utf-8"))

mms_languages = json.load(open("mms_languages.json", encoding="utf-8"))

parser = argparse.ArgumentParser()
parser.add_argument(
    "-t",
    "--text-id",
    help="The id for the bb text translation to use.",
    required=True,
)
parser.add_argument(
    "-a",
    "--audio-id",
    help="The id for the bb audio translation to use.",
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


def get_chapter(
    folder: str, bb_text_id: str, bb_audio_id: str, chapter_id: str
) -> tuple[File, File]:
    spinner = Halo("Fetching text...").start()
    book, chapter = chapter_id.split(".")

    if not os.path.exists(f"{folder}/{chapter_id}.json"):
        req = urllib.request.Request(
            f"https://4.dbt.io/api/download/{bb_text_id}/{book}/{chapter}?&v=4&key={os.getenv('BIBLE_BRAIN_API_KEY', '')}"
        )
        resp = urllib.request.urlopen(req).read()
        json_response = json.loads(resp.decode("utf-8"))

        for verse in json_response["data"]:
            verse_id = f"{book}.{chapter}.{verse['verse_start']}"
            if verse["verse_start"] != verse["verse_end"]:
                verse_id += f"-{book}.{chapter}.{verse['verse_end']}"

        # TEXT

        verses: list[Verse] = []

        for verse in json_response["data"]:
            verse_id = f"{book}.{chapter}.{verse['verse_start']}"
            if verse["verse_start"] != verse["verse_end"]:
                verse_id += f"-{book}.{chapter}.{verse['verse_end']}"

            verses.append(
                {
                    "verse_id": verse_id,
                    "text": verse["verse_text"],
                }
            )

        json.dump(verses, open(f"{folder}/{chapter_id}.json", "w", encoding="utf-8"))

    # AUDIO

    spinner.text = "Fetching audio..."

    if not os.path.exists(f"{folder}/{chapter_id}.mp3"):
        fetch_url = f"https://4.dbt.io/api/download/{bb_audio_id}/{book}/{chapter}?&v=4&key={os.getenv('BIBLE_BRAIN_API_KEY', '')}"

        req = urllib.request.Request(fetch_url)
        resp = urllib.request.urlopen(req).read()
        json_response = json.loads(resp.decode("utf-8"))
        urllib.request.urlretrieve(
            json_response["data"][0]["path"],
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
            print("Invalid language detected.")
            exit(0)

    model, dictionary = load_model()

    matched_files = []

    for chapter in bible_chapters:
        if "MAT.28" not in chapter:
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

    if timestamps is None:
        print("Failed to align timestamps.")
        exit(0)

    for chapter in timestamps:
        json.dump(
            chapter["sections"],
            open(f"{output}/{chapter['text_file']}", "w", encoding="utf-8"),
        )


main()
