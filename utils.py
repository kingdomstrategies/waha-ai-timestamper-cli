import json
import os
import re
import time
import traceback
from typing import Any

import ffmpeg
from halo import Halo

from lid import identify_language
from mms.align_utils import get_alignments, get_spans, get_uroman_tokens
from mms.text_normalization import text_normalize
from timestamp_types import File, FileTimestamps, Match, Section

mms_languages = json.load(open("mms_languages.json"))


def match_files(
    files: list[File],
) -> list[Match]:
    """
    Match audio and text files by name (without extension).
    """

    audio_extensions = {".wav", ".mp3"}
    text_extensions = {".txt", ".usfm"}

    # Dictionary to store matched files by name (without extension)
    matched_files = {}

    for file_name, path in files:
        name, ext = file_name.rsplit(".", 1)

        ext = f".{ext}"

        if ext in audio_extensions:
            if name not in matched_files:
                matched_files[name] = (None, None)
            matched_files[name] = (
                (file_name, path),
                matched_files[name][1],
            )  # Store audio file
        elif ext in text_extensions:
            if name not in matched_files:
                matched_files[name] = (None, None)
            matched_files[name] = (
                matched_files[name][0],
                (file_name, path),
            )  # Store text file

    # Filter out pairs where either the audio or text is missing
    return [match for match in matched_files.values() if None not in match]


def align_matches(
    folder: str,
    language: str | None,
    separator: str,
    matches: list[Match],
    model: Any,
    dictionary: Any,
):
    """
    Align audio and text files and write output to Firestore.
    """
    spinner = Halo("Aligning...").start()

    file_timestamps: list[FileTimestamps] = []

    progress = 0
    total_length = 0

    for index, match in enumerate(matches):
        if match[0] is None or match[1] is None:
            continue
        try:
            audio_path = match[0][1]
            audio_type = match[0][0].split(".")[-1]

            wav_output = audio_path.replace(f".{audio_type}", "_output.wav")

            spinner.text = f"Converting audio to {wav_output}..."
            spinner.start()

            total_length += float(ffmpeg.probe(audio_path)["streams"][0]["duration"])
            stream = ffmpeg.input(audio_path)
            stream = ffmpeg.output(stream, wav_output, acodec="pcm_s16le", ar=16000)
            stream = ffmpeg.overwrite_output(stream)
            ffmpeg.run(
                stream,
                overwrite_output=True,
                cmd=["ffmpeg", "-loglevel", "error"],  # type: ignore
            )
            spinner.succeed(f"Audio converted to {wav_output}.")

            # Identify the session language. This is time
            # consuming so we only do it for the first file and assume
            # all files are the same language.
            if index == 0 and language is None:
                # Cut down audio to 10 seconds for language
                # identification.
                spinner.text = "Identifying language..."
                spinner.start()
                cut_output = f"{folder}/cut_output.wav"
                stream = ffmpeg.input(wav_output)
                stream = ffmpeg.output(stream, cut_output, t=30)
                stream = ffmpeg.overwrite_output(stream)
                ffmpeg.run(
                    stream,
                    overwrite_output=True,
                    cmd=["ffmpeg", "-loglevel", "error"],  # type: ignore
                )

                language = identify_language(cut_output)

                # Check if language is valid.
                language_match = next(
                    (item for item in mms_languages if item["iso"] == language), None
                )

                if language_match is None or not language_match["align"]:
                    spinner.fail(f"Detected language {language} not supported.")
                    return
                else:
                    spinner.succeed(f"Valid language identified as {language}.")

                # Remove the cut file
                os.remove(cut_output)

            text_path = match[1][1]

            text_extension = match[1][0].split(".")[-1]

            text_file = open(text_path, "r", encoding="utf-8")
            lines_to_timestamp = []

            if text_extension == "json":
                verses = json.load(text_file)
                for verse in verses:
                    lines_to_timestamp.append(verse["text"])

            elif text_extension == "txt":
                # Read the separator from the query parameter and adjust
                # it so it can be used in the split function.
                if separator == "lineBreak":
                    separator = "\n"
                elif separator == "squareBracket":
                    separator = "["
                elif separator == "downArrow":
                    separator = "⬇️"

                lines_to_timestamp = text_file.read().split(separator)
            elif text_extension == "usfm":
                # Define the tags to ignore
                ignore_tags = [
                    "\\c",
                    "\\p",
                    "\\s",
                    "\\s1",
                    "\\s2",
                    "\\f",
                    "\\ft",
                    "\\fr",
                    "\\x",
                    "\\xt",
                    "\\xo",
                    "\\r",
                    "\\t",
                    "\\m",
                ]

                # Compile a regex to match tags we want to ignore
                ignore_regex = re.compile(
                    r"|".join(re.escape(tag) for tag in ignore_tags)
                )
                current_verse = ""
                for line in text_file:
                    if ignore_regex.match(line.strip()):
                        continue

                    if line.startswith(r"\v"):  # USFM verse marker
                        if current_verse:
                            cleaned_verse = re.sub(
                                r"\\[a-z]+\s?", "", current_verse.strip()
                            )
                            lines_to_timestamp.append(cleaned_verse)
                        current_verse = line.strip()  # Start a new verse
                    else:
                        current_verse += " " + line.strip()

                if current_verse:  # Append the last verse after the loop
                    cleaned_verse = re.sub(r"\\[a-z]+\s?", "", current_verse.strip())
                    lines_to_timestamp.append(cleaned_verse)

            norm_lines_to_timestamp = [
                text_normalize(
                    line.strip(), language if language is not None else "eng"
                )
                for line in lines_to_timestamp
            ]
            uroman_lines_to_timestamp = get_uroman_tokens(
                norm_lines_to_timestamp, language
            )
            uroman_lines_to_timestamp = ["<star>"] + uroman_lines_to_timestamp
            lines_to_timestamp = ["<star>"] + lines_to_timestamp
            norm_lines_to_timestamp = ["<star>"] + norm_lines_to_timestamp
            spinner.succeed("Text normalized and romanized.")

            spinner.text = "Aligning..."
            spinner.start()

            segments, stride = get_alignments(
                wav_output,
                uroman_lines_to_timestamp,
                model,
                dictionary,
            )

            spans = get_spans(uroman_lines_to_timestamp, segments)

            sections = []

            for i, t in enumerate(lines_to_timestamp):
                span = spans[i]
                seg_start_idx = span[0].start
                seg_end_idx = span[-1].end

                audio_start_sec = seg_start_idx * stride / 1000
                audio_end_sec = seg_end_idx * stride / 1000

                section: Section = {
                    "begin": audio_start_sec,
                    "end": audio_end_sec,
                    "begin_str": time.strftime(
                        "%H:%M:%S", time.gmtime(audio_start_sec)
                    ),
                    "end_str": time.strftime("%H:%M:%S", time.gmtime(audio_end_sec)),
                    "text": t,
                    "uroman_tokens": uroman_lines_to_timestamp[i],
                }

                sections.append(section)
        except Exception:
            spinner.fail("Failed to align.")
            print(traceback.format_exc())
            return

        spinner.succeed("Alignment done.")

        spinner.text = "Cleaning up..."
        spinner.start()
        os.remove(wav_output)
        spinner.succeed("Cleaned up.")

        file_timestamps.append(
            {
                "audio_file": match[0][0],
                "text_file": match[1][0],
                "sections": sections,
            }
        )
        progress += 1

    return file_timestamps
