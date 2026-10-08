from scout.voice.tts import _init_kokoro
_init_kokoro()
from scout.voice.tts import _kokoro
print("Phonemes 'I\\'m Scout.':", ascii(_kokoro.tokenizer.phonemize("I'm Scout.", "en-us")))
print("Phonemes 'I am Scout.':", ascii(_kokoro.tokenizer.phonemize("I am Scout.", "en-us")))
