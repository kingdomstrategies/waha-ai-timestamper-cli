import torch
import torchaudio
from transformers import AutoFeatureExtractor, Wav2Vec2ForSequenceClassification

model_id = "facebook/mms-lid-4017"

processor = AutoFeatureExtractor.from_pretrained(model_id)
model = Wav2Vec2ForSequenceClassification.from_pretrained(model_id)


# Load the MP3 file and convert to the correct format
def load_audio(file_path: str):
    # Load the audio file (returns waveform, sample rate)
    waveform, sample_rate = torchaudio.load(file_path)

    # Resample to 16000 Hz if necessary (the model expects 16kHz audio)
    if sample_rate != 16000:
        waveform = torchaudio.transforms.Resample(
            orig_freq=sample_rate, new_freq=16000
        )(waveform)

    return waveform.squeeze(), 16000


# Function to identify the language of an audio file
def identify_language(audio_path: str):
    waveform, sample_rate = load_audio(audio_path)

    # Process the waveform to match the input expected by the model
    inputs = processor(waveform, sampling_rate=sample_rate, return_tensors="pt")

    # Forward pass through the model
    with torch.no_grad():
        logits = model(**inputs).logits

    # Get the predicted language ID (class with the highest score)
    predicted_id = torch.argmax(logits, dim=-1).item()

    # Convert the predicted ID to the corresponding language label
    language = model.config.id2label[int(predicted_id)]

    return language
