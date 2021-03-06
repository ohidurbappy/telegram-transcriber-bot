import requests
import traceback
import pydub
import io
from pydub import AudioSegment
from config import Config

config=Config()

WIT_API_TOKEN=config.wit_api_token


def __transcribe_chunk(chunk, lang):
  if lang not in ['en']:
    return None

  
  
  headers = {
    'authorization': 'Bearer ' + WIT_API_TOKEN,
    'accept': 'application/vnd.wit.20180705+json',
    'content-type': 'audio/raw;encoding=signed-integer;bits=16;rate=8000;endian=little',
  }

  text = None
  try: 
    request = requests.request(
      "POST",
      "https://api.wit.ai/speech", 
      headers=headers, 
      params = {'verbose': True},
      data=io.BufferedReader(io.BytesIO(chunk.raw_data))
    )

    res = request.json()
  
    if '_text' in res:
      text = res['_text']
    elif 'text' in res:  # Changed in may 2020
      text = res['text']

  except Exception as e:
    traceback.print_exc()
    return None

  return text

def __generate_chunks(segment, length=20000/1001, split_on_silence=False, noise_threshold=-36): 
  chunks = list()
  if split_on_silence is False:
    for i in range(0, len(segment), int(length*1000)):
      chunks.append(segment[i:i+int(length*1000)])
  else:
    while len(chunks) < 1:
      chunks = pydub.silence.split_on_silence(segment, noise_threshold)
      noise_threshold += 4
    
    for i, chunk in enumerate(chunks):
      if len(chunk) > int(length*1000):
        subchunks = __generate_chunks(chunk, length, split_on_silence, noise_threshold+4)
        chunks = chunks[:i-1] + subchunks + chunks[i+1:]

  return chunks

def __preprocess_audio(audio):
  return audio.set_sample_width(2).set_channels(1).set_frame_rate(8000)

def transcribe(path, lang):
  audio = AudioSegment.from_file(path)

  chunks = __generate_chunks(__preprocess_audio(audio))

  for i, chunk in enumerate(chunks):
    r = __transcribe_chunk(chunk, lang)

    if r is not None:
      yield r
