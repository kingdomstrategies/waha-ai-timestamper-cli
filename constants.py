import json

from dotenv import load_dotenv

from timestamp_types import BbTranslation, MmsLanguage

model_name = "ctc_alignment_mling_uroman_model.pt"
model_url = (
    "https://dl.fbaipublicfiles.com/mms/torchaudio/ctc_alignment_mling_uroman/model.pt"
)
dict_name = "ctc_alignment_mling_uroman_model.dict"
dict_url = "https://dl.fbaipublicfiles.com/mms/torchaudio/ctc_alignment_mling_uroman/dictionary.txt"

NT_BOOKS = [
    "MAT",
    "MRK",
    "LUK",
    "JHN",
    "ACT",
    "ROM",
    "1CO",
    "2CO",
    "GAL",
    "EPH",
    "PHP",
    "COL",
    "1TH",
    "2TH",
    "1TI",
    "2TI",
    "TIT",
    "PHM",
    "HEB",
    "JAS",
    "1PE",
    "2PE",
    "1JN",
    "2JN",
    "3JN",
    "JUD",
    "REV",
]

load_dotenv()

bible_chapters: list[str] = json.load(
    open("data/bible_chapters.json", encoding="utf-8")
)
bb_translations: list[BbTranslation] = json.load(
    open("data/bb_translations.json", encoding="utf-8")
)
mms_languages: list[MmsLanguage] = json.load(
    open("data/mms_languages.json", encoding="utf-8")
)
