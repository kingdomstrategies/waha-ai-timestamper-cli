"""
Types for the timestamping service.
"""

from enum import Enum
from typing import TypedDict


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
    verse_id: str
    text: str
