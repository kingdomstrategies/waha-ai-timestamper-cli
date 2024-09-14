import math
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, List, TypedDict, Union

import sox
import torch
import torchaudio
import torchaudio.functional as F
from torchaudio.models import wav2vec2_model

from constants import dict_name, model_name

SAMPLING_FREQ = 16000
EMISSION_INTERVAL = 30
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class MMSSegment(TypedDict):
    begin: float
    end: float
    text: str
    uroman_tokens: str


# iso codes with specialized rules in uroman
special_isos_uroman = [
    "ara",
    "bel",
    "bul",
    "deu",
    "ell",
    "eng",
    "fas",
    "grc",
    "ell",
    "eng",
    "heb",
    "kaz",
    "kir",
    "lav",
    "lit",
    "mkd",
    "mkd2",
    "oss",
    "pnt",
    "pus",
    "rus",
    "srp",
    "srp2",
    "tur",
    "uig",
    "ukr",
    "yid",
]


def normalize_uroman(text: str):
    text = text.lower()
    text = re.sub("([^a-z' ])", " ", text)
    text = re.sub(" +", " ", text)
    return text.strip()


def get_uroman_tokens(norm_transcripts: List[str], iso: Union[str, None] = None):
    normalized_file = tempfile.NamedTemporaryFile()
    uroman_file = tempfile.NamedTemporaryFile()

    with open(normalized_file.name, "w", encoding="utf-8") as f:
        for t in norm_transcripts:
            f.write(t + "\n")

    cmd = ["uroman", "-i", normalized_file.name, "-o", uroman_file.name]
    if iso and iso in special_isos_uroman:
        cmd.append("-l")
        cmd.append(iso)

    subprocess.run(cmd, check=True)

    outtexts = []
    with open(uroman_file.name, encoding="utf-8") as f:
        for line in f:
            line = " ".join(line.strip())
            line = re.sub(r"\s+", " ", line).strip()
            outtexts.append(line)
    assert len(outtexts) == len(norm_transcripts)
    uromans: List[str] = []
    for ot in outtexts:
        uromans.append(normalize_uroman(ot))
    return uromans


@dataclass
class Segment:
    label: str
    start: int
    end: int

    def __repr__(self):
        return f"{self.label}: [{self.start:5d}, {self.end:5d})"

    @property
    def length(self):
        return self.end - self.start


def merge_repeats(path: List[Any], idx_to_token_map: dict[int, str]):
    i1, i2 = 0, 0
    segments: List[Segment] = []
    while i1 < len(path):
        while i2 < len(path) and path[i1] == path[i2]:
            i2 += 1
        segments.append(Segment(idx_to_token_map[path[i1]], i1, i2 - 1))
        i1 = i2
    return segments


def time_to_frame(time: float):
    stride_msec = 20
    frames_per_sec = 1000 / stride_msec
    return int(time * frames_per_sec)


def get_spans(tokens: List[str], segments: List[Segment]):
    ltr_idx = 0
    tokens_idx = 0
    intervals = []
    start, end = (0, 0)
    sil = "<blank>"
    for seg_idx, seg in enumerate(segments):
        if tokens_idx == len(tokens):
            assert seg_idx == len(segments) - 1
            assert seg.label == "<blank>"
            continue
        cur_token = tokens[tokens_idx].split(" ")
        ltr = cur_token[ltr_idx]
        if seg.label == "<blank>":
            continue
        assert seg.label == ltr
        if (ltr_idx) == 0:
            start = seg_idx
        if ltr_idx == len(cur_token) - 1:
            ltr_idx = 0
            tokens_idx += 1
            intervals.append((start, seg_idx))
            while tokens_idx < len(tokens) and len(tokens[tokens_idx]) == 0:
                intervals.append((seg_idx, seg_idx))
                tokens_idx += 1
        else:
            ltr_idx += 1
    spans: List[List[Segment]] = []
    for idx, (start, end) in enumerate(intervals):
        span = segments[start : end + 1]
        if start > 0:
            prev_seg = segments[start - 1]
            if prev_seg.label == sil:
                pad_start = (
                    prev_seg.start
                    if (idx == 0)
                    else int((prev_seg.start + prev_seg.end) / 2)
                )
                span = [Segment(sil, pad_start, span[0].start)] + span
        if end + 1 < len(segments):
            next_seg = segments[end + 1]
            if next_seg.label == sil:
                pad_end = (
                    next_seg.end
                    if (idx == len(intervals) - 1)
                    else math.floor((next_seg.start + next_seg.end) / 2)
                )
                span = span + [Segment(sil, span[-1].end, pad_end)]
        spans.append(span)
    return spans


def generate_emissions(model: Any, audio_file: str):
    waveform, _ = torchaudio.load(audio_file)  # waveform: channels X T
    waveform = waveform.to(DEVICE)
    total_duration = sox.file_info.duration(audio_file)

    assert total_duration, "Could not get duration of audio file"

    audio_sf = sox.file_info.sample_rate(audio_file)
    assert audio_sf == SAMPLING_FREQ

    emissions_arr = []
    with torch.inference_mode():
        i: float = 0
        while i < total_duration:
            segment_start_time, segment_end_time = (i, i + EMISSION_INTERVAL)

            context = EMISSION_INTERVAL * 0.1
            input_start_time = max(segment_start_time - context, 0)
            input_end_time = min(segment_end_time + context, total_duration)
            waveform_split = waveform[
                :,
                int(SAMPLING_FREQ * input_start_time) : int(
                    SAMPLING_FREQ * (input_end_time)
                ),
            ]

            model_outs, _ = model(waveform_split)
            emissions_ = model_outs[0]
            emission_start_frame = time_to_frame(segment_start_time)
            emission_end_frame = time_to_frame(segment_end_time)
            offset = time_to_frame(input_start_time)

            emissions_ = emissions_[
                emission_start_frame - offset : emission_end_frame - offset, :
            ]
            emissions_arr.append(emissions_)
            i += EMISSION_INTERVAL

    emissions = torch.cat(emissions_arr, dim=0).squeeze()
    emissions = torch.log_softmax(emissions, dim=-1)

    stride = float(waveform.size(1) * 1000 / emissions.size(0) / SAMPLING_FREQ)

    return emissions, stride


def get_alignments(
    audio_file: str,
    tokens: List[str],
    model: Any,
    dictionary: dict[str, int],
):

    # Generate emissions
    emissions, stride = generate_emissions(model, audio_file)
    T, _ = emissions.size()

    emissions = torch.cat([emissions, torch.zeros(T, 1).to(DEVICE)], dim=1)

    # Force Alignment
    if tokens:
        token_indices = [
            dictionary[c] for c in " ".join(tokens).split(" ") if c in dictionary
        ]
    else:
        print(f"Empty transcript for audio file {audio_file}.")
        token_indices = []

    blank = dictionary["<blank>"]

    targets = torch.tensor(token_indices, dtype=torch.int32).to(DEVICE)

    input_lengths = torch.tensor(emissions.shape[0]).unsqueeze(-1)
    target_lengths = torch.tensor(targets.shape[0]).unsqueeze(-1)

    path, _ = F.forced_align(
        emissions.unsqueeze(0),
        targets.unsqueeze(0),
        input_lengths,
        target_lengths,
        blank=blank,
    )

    path = path.squeeze().to("cpu").tolist()
    idx_to_token_map = {v: k for k, v in dictionary.items()}
    segments = merge_repeats(path, idx_to_token_map)

    return segments, stride


def get_model_and_dict():
    state_dict = torch.load(model_name, map_location="cpu", weights_only=True)

    model = wav2vec2_model(
        extractor_mode="layer_norm",
        extractor_conv_layer_config=[
            (512, 10, 5),
            (512, 3, 2),
            (512, 3, 2),
            (512, 3, 2),
            (512, 3, 2),
            (512, 2, 2),
            (512, 2, 2),
        ],
        extractor_conv_bias=True,
        encoder_embed_dim=1024,
        encoder_projection_dropout=0.0,
        encoder_pos_conv_kernel=128,
        encoder_pos_conv_groups=16,
        encoder_num_layers=24,
        encoder_num_heads=16,
        encoder_attention_dropout=0.0,
        encoder_ff_interm_features=4096,
        encoder_ff_interm_dropout=0.1,
        encoder_dropout=0.0,
        encoder_layer_norm_first=True,
        encoder_layer_drop=0.1,
        aux_num_out=31,
    )
    model.load_state_dict(state_dict)
    model.eval()

    dictionary = {}
    with open(dict_name, encoding="utf-8") as f:
        dictionary = {l.strip(): i for i, l in enumerate(f.readlines())}

    return model, dictionary
