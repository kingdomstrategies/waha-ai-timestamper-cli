import json
import os
import time
import urllib.request
from typing import Any, Union

import ffmpeg
from halo import Halo

from constants import NT_BOOKS
from mms.align_utils import get_alignments, get_spans, get_uroman_tokens
from mms.text_normalization import text_normalize
from timestamp_types import ChapterInfo, ChapterText, Verse


def get_chapter_info(
    chapter_id: str,
    path_to_audio_bible: str,
) -> ChapterInfo:
    book_id = chapter_id.split(".")[0]
    chapter_number = chapter_id.split(".")[1]

    return {
        "book_id": book_id,
        "chapter_id": chapter_id,
        "chapter_number": chapter_number,
        "paths": {
            "book": f"{path_to_audio_bible}/{book_id}",
            "audio": f"{path_to_audio_bible}/{book_id}/{book_id}_{chapter_number.zfill(3)}.mp3",
            "text": f"{path_to_audio_bible}/{book_id}/{book_id}_{chapter_number.zfill(3)}.json",
        },
        "testament": "nt" if book_id in NT_BOOKS else "ot",
    }


def get_dbl_text(
    dbl_id: str,
    chapter_id: str,
    chapter_text: ChapterText,
    output: str,
):
    def add_dbl_text(chapter_text: ChapterText, item: Any):
        """API.Bible-specific function to add text to the chapter object."""

        if "attrs" in item and "verseId" in item["attrs"]:
            verseId: str = item["attrs"]["verseId"]

            existing_element: Union[Verse, None] = None

            for verse in chapter_text["verses"]:
                if verse["verseId"] == verseId:
                    existing_element = verse

            if existing_element is not None:
                existing_element["text"] += item["text"]
            else:
                chapter_text["verses"].append(
                    {
                        "verseId": verseId,
                        "text": item["text"],
                    }
                )

    spinner = Halo(
        f"({chapter_id}) Getting text from dbl...",
    ).start()

    try:
        req = urllib.request.Request(
            "https://api.scripture.api.bible/v1"
            f"/bibles/{dbl_id}"
            f"/chapters/{chapter_id}"
            "?content-type=json&include-notes=false&include-titles=true"
            "&include-chapter-numbers=false&include-verse-numbers=true"
            "&include-verse-spans=false"
        )
        req.add_header("api-key", os.getenv("API_BIBLE_KEY", ""))
        resp = urllib.request.urlopen(req).read()
        json_response = json.loads(resp.decode("utf-8"))

        # Iterate through reponse and add all text to an object.
        for verse_chunk in json_response["data"]["content"]:
            for item1 in verse_chunk["items"]:
                if "items" in item1:
                    for item2 in item1["items"]:
                        if "items" in item2:
                            for item3 in item2["items"]:
                                add_dbl_text(chapter_text, item3)
                        else:
                            add_dbl_text(chapter_text, item2)
                else:
                    add_dbl_text(chapter_text, item1)

        chapter_text["reference"] = json_response["data"]["reference"]
        chapter_text["bookName"] = " ".join(
            json_response["data"]["reference"].split(" ")[:-1]
        )
    except Exception as e:
        spinner.fail(f"({chapter_id}) Failed to get text from dbl. Error: {e}.")
        return
    spinner.succeed(f"({chapter_id}) Got text from dbl.")
    json.dump(chapter_text, open(output, "w", encoding="utf-8"), indent=2)


def get_bb_text(bb_id: str, chapter_id: str, chapter_text: ChapterText, output: str):
    spinner = Halo(
        f"({chapter_id}) Getting text from bb...",
    ).start()

    book, chapter = chapter_id.split(".")

    try:
        req = urllib.request.Request(
            f"https://4.dbt.io/api/download/{bb_id}/{book}/{chapter}?&v=4&key={os.getenv('BIBLE_BRAIN_API_KEY', '')}"
        )
        resp = urllib.request.urlopen(req).read()
        json_response = json.loads(resp.decode("utf-8"))

        for verse in json_response["data"]:
            verseId = f"{book}.{chapter}.{verse['verse_start']}"
            if verse["verse_start"] != verse["verse_end"]:
                verseId += f"-{book}.{chapter}.{verse['verse_end']}"

            chapter_text["verses"].append(
                {
                    "verseId": verseId,
                    "text": verse["verse_text"],
                }
            )
        chapter_text["reference"] = (
            f"{json_response['data'][0]['book_name_alt']} {chapter}"
        )
        chapter_text["bookName"] = json_response["data"][0]["book_name_alt"]
    except Exception as e:
        spinner.fail(f"({chapter_id}) Failed to get text from bb. Error: {e}.")
        return
    spinner.succeed(f"({chapter_id}) Got text from bb.")
    json.dump(chapter_text, open(output, "w", encoding="utf-8"), indent=2)


def get_dbl_audio(dbl_id: str, chapter_id: str, output: str):
    spinner = Halo(f"({chapter_id}) Getting audio from dbl...").start()

    fetch_url = (
        "https://api.scripture.api.bible/v1"
        f"/audio-bibles/{dbl_id}"
        f"/chapters/{chapter_id}"
    )

    try:
        req = urllib.request.Request(fetch_url)
        req.add_header("api-key", os.getenv("API_BIBLE_KEY", ""))
        resp = urllib.request.urlopen(req).read()
        json_response = json.loads(resp.decode("utf-8"))
    except Exception as e:
        spinner.fail(f"({chapter_id}) Failed to get audio from dbl. Error: {e}.")
        return
    try:
        urllib.request.urlretrieve(json_response["data"]["resourceUrl"], output)
    except Exception as e:
        spinner.fail(f"({chapter_id}) Failed to download audio from dbl. Error: {e}.")
        return

    spinner.succeed(f"({chapter_id}) Got audio from dbl.")


def get_yv_audio(yv_id: str, chapter_id: str, output: str):
    spinner = Halo(f"({chapter_id}) Getting audio from yv...").start()

    fetch_url = (
        "https://audio-bible.youversionapi.com/3.1/chapter.json"
        "?version_id="
        f"{yv_id}"
        f"&reference={chapter_id}"
    )
    try:
        req = urllib.request.Request(fetch_url)
        resp = urllib.request.urlopen(req).read()
        json_response = json.loads(resp.decode("utf-8"))
    except Exception as e:
        spinner.fail(f"({chapter_id}) Failed to get audio from yv. Error: {e}.")
        return

    try:
        urllib.request.urlretrieve(
            f"https:{json_response['response']['data'][0]['download_urls']['format_mp3_32k']}",
            output,
        )
    except Exception as e:
        spinner.fail(f"({chapter_id}) Failed to download audio from yv. Error: {e}.")
        return
    spinner.succeed(f"({chapter_id}) Got audio from yv.")


def get_bb_audio(bb_id: str, chapter_id: str, output: str):
    spinner = Halo(f"({chapter_id}) Getting audio from bb...").start()
    book, chapter = chapter_id.split(".")
    fetch_url = f"https://4.dbt.io/api/download/{bb_id}/{book}/{chapter}?&v=4&key={os.getenv('BIBLE_BRAIN_API_KEY', '')}"
    try:
        req = urllib.request.Request(fetch_url)
        resp = urllib.request.urlopen(req).read()
        json_response = json.loads(resp.decode("utf-8"))
    except Exception as e:
        spinner.fail(f"({chapter_id}) Failed to get audio from bb. Error: {e}.")
        return

    try:
        urllib.request.urlretrieve(json_response["data"][0]["path"], output)
    except Exception as e:
        spinner.fail(f"({chapter_id}) Failed to download audio from bb. Error: {e}.")
        return
    spinner.succeed(f"({chapter_id}) Got audio from bb.")


def get_timings(
    lang: str,
    chapter_info: ChapterInfo,
    model: Any,
    dictionary: Any,
):
    spinner = Halo(text=f"({chapter_info['chapter_id']}) Aligning...").start()

    if not os.path.exists(chapter_info["paths"]["text"]):
        spinner.fail(
            f"({chapter_info['chapter_id']}) No text file found. Skipping alignment."
        )
        return

    chapter_text: ChapterText = json.load(
        open(chapter_info["paths"]["text"], encoding="utf-8")
    )

    if len(chapter_text["verses"]) == 0:
        spinner.fail(
            f"({chapter_info['chapter_id']}) Text file exists but has no bible text. Skipping alignment."
        )
        return
    elif chapter_text["verses"][0].get("timings") is not None:
        spinner.info(
            f"({chapter_info['chapter_id']}) Timing data already exists. Skipping."
        )
        return
    elif not os.path.exists(chapter_info["paths"]["audio"]):
        spinner.fail(
            f"({chapter_info['chapter_id']}) No audio found. Skipping alignment."
        )
        return

    audio_type = chapter_info["paths"]["audio"].split(".")[-1]
    wav_output = chapter_info["paths"]["audio"].replace(f".{audio_type}", "_output.wav")
    spinner.text = f"({chapter_info['chapter_id']}) Converting audio to wav..."

    stream = ffmpeg.input(chapter_info["paths"]["audio"])
    stream = ffmpeg.output(stream, wav_output, acodec="pcm_s16le", ar=16000)
    stream = ffmpeg.overwrite_output(stream)
    ffmpeg.run(
        stream,
        overwrite_output=True,
        cmd=["ffmpeg", "-loglevel", "error"],  # type: ignore
    )

    spinner.text = f"({chapter_info['chapter_id']}) Normalizing text..."
    lines_to_timestamp = []

    for verse in chapter_text["verses"]:
        lines_to_timestamp.append(verse["text"])

    norm_lines_to_timestamp = [
        text_normalize(line.strip(), lang) for line in lines_to_timestamp
    ]
    uroman_lines_to_timestamp = get_uroman_tokens(norm_lines_to_timestamp, lang)
    uroman_lines_to_timestamp = ["<star>"] + uroman_lines_to_timestamp
    lines_to_timestamp = ["<star>"] + lines_to_timestamp
    norm_lines_to_timestamp = ["<star>"] + norm_lines_to_timestamp

    spinner.text = f"({chapter_info['chapter_id']}) Aligning..."

    segments, stride = get_alignments(
        wav_output,
        uroman_lines_to_timestamp,
        model,
        dictionary,
    )

    spans = get_spans(uroman_lines_to_timestamp, segments)

    for i, _ in enumerate(lines_to_timestamp):
        if i == 0:
            continue
        matching_verse = chapter_text["verses"][i - 1]
        span = spans[i]
        seg_start_idx = span[0].start
        seg_end_idx = span[-1].end

        audio_start_sec = seg_start_idx * stride / 1000
        audio_end_sec = seg_end_idx * stride / 1000

        matching_verse["timings"] = (round(audio_start_sec, 2), round(audio_end_sec, 2))
        matching_verse["timings_str"] = (
            time.strftime("%H:%M:%S", time.gmtime(audio_start_sec)),
            time.strftime("%H:%M:%S", time.gmtime(audio_end_sec)),
        )
        matching_verse["uroman"] = uroman_lines_to_timestamp[i]

    json.dump(
        chapter_text,
        open(chapter_info["paths"]["text"], "w", encoding="utf-8"),
        indent=2,
    )

    spinner.text = f"({chapter_info['chapter_id']}) Cleaning up..."
    spinner.start()
    os.remove(wav_output)
    spinner.succeed(f"({chapter_info['chapter_id']}) Aligned.")
