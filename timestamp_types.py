"""
Types for the timestamping service.
"""

from enum import Enum
from typing import Literal, NotRequired, Optional, TypedDict


class Section(TypedDict):
    """
    A single section of a match with timestamp data.
    """

    verse_id: str
    timings: tuple[float, float]
    timings_str: tuple[str, str]
    text: str
    uroman_tokens: str


class FileTimestamps(TypedDict):
    """
    Generated timestamp for a match.
    """

    audio_file: str
    text_file: str
    sections: list[Section]


# Info for a file. Elements are name, url, and path.
File = tuple[str, str]

# A match consists of an audio file and a text file.
Match = tuple[File | None, File | None]


class Status(Enum):
    """
    Status of a session.
    """

    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class SessionDoc(TypedDict):
    """
    Session document.
    """

    sessionId: str
    status: Status
    timestamps: FileTimestamps | None


class Verse(TypedDict):
    text: str
    timings: NotRequired[Optional[tuple[float, float]]]
    timings_str: NotRequired[Optional[tuple[str, str]]]
    uroman: NotRequired[Optional[str]]
    verseId: str


class ChapterText(TypedDict):
    bookName: str
    chapterId: str
    reference: str
    translationId: str
    """
  An id used to represent a bible translation. The standard abbreviation for a translation should be used if there is one.
  """
    verses: list[Verse]


class ChapterPaths(TypedDict):
    book: str
    audio: str
    text: str


class ChapterInfo(TypedDict):
    """An object to store a bunch of useful information about a specific bible chapter in a specific scripture translation."""

    chapter_id: str
    book_id: str
    chapter_number: str
    testament: Literal["ot", "nt"]
    paths: ChapterPaths


class TranslationIds(TypedDict):
    audio: str
    text: str


class Translation(TypedDict):
    source: Literal["bb", "dbl"]
    languageId: str
    languageName: str
    translationId: str
    translationName: str
    ot: TranslationIds | None
    nt: TranslationIds | None


class MmsLanguage(TypedDict):
    align: bool
    iso: str
    name: str
    identify: bool
    tts: bool
