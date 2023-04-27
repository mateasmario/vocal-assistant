import pandas as pd
import time
import boto3
import os
import wave
from pvrecorder import PvRecorder
import struct
import gtts
import sounddevice as sd
import soundfile as sf
import spacy
from collections import Counter
from string import punctuation
import en_core_web_md


AWS_ACCESS_KEY_ID = ""
AWS_SECRET_ACCESS_KEY = ""

ANSWER_FILE_NAME = "answer.wav"
BOOP_FILE_NAME = "boop.mp3"
DING_FILE_NAME = "ding.mp3"

GENERIC_ANSWER = "I'm sorry, but I didn't understand the question. Could you please try again?"

def playaudio(path, wait):
    data, fs = sf.read(path, dtype='float32')  
    sd.play(data, fs)

    if wait == True:
        status = sd.wait()

def check_job_name(job_name, transcribe):
    existed_jobs = transcribe.list_transcription_jobs()
    for job in existed_jobs['TranscriptionJobSummaries']:
        if job_name == job['TranscriptionJobName']:
            return False
    return True

def amazon_transcribe(audio_file_name, transcribe):
    job_uri = "s3://dianamarioawsbucket/" + audio_file_name

    timestamp = os.path.getmtime(audio_file_name)
    job_name = (audio_file_name.split('.')[0]).replace(" ", "") + str(timestamp)
    
    file_format = audio_file_name.split('.')[1]

    if (check_job_name(job_name, transcribe) == False):
        raise Exception("There was a problem in creating a job with a unique name.")

    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': job_uri},
        MediaFormat = file_format,
        LanguageCode='en-US')

    while True:
        result = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        if result['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
            break
        time.sleep(2)
    if result['TranscriptionJob']['TranscriptionJobStatus'] == "COMPLETED":
        data = pd.read_json(result['TranscriptionJob']['Transcript']['TranscriptFileUri'])
        return data['results'][1][0]['transcript']

def get_hotwords(text):
    nlp = en_core_web_md.load()
    result = []
    pos_tag = ['PROPN', 'ADJ', 'NOUN'] # 1
    doc = nlp(text.lower()) # 2
    for token in doc:
        # 3
        if(token.text in nlp.Defaults.stop_words or token.text in punctuation):
            continue
        # 4
        if(token.pos_ in pos_tag):
            result.append(token.text)
                
    return result # 5

def get_answer(text):    
    processed_text = set(get_hotwords(text))
    print(processed_text)

    return GENERIC_ANSWER

def main():
    transcribe = boto3.client("transcribe", 
                aws_access_key_id = AWS_ACCESS_KEY_ID, 
                aws_secret_access_key = AWS_SECRET_ACCESS_KEY, 
                region_name = "eu-central-1")

    recorder = PvRecorder(device_index=-1, frame_length=512)
    audio = []

    try:
        recorder.start()

        while True:
            frame = recorder.read()
            audio.extend(frame)
    except KeyboardInterrupt:
        recorder.stop()

        with wave.open("audio.wav", 'w') as f:
            
            # Save audio file on local drive
            print("[1] Saving audio file on local drive...")
            playaudio(BOOP_FILE_NAME, wait=False)
            f.setparams((1, 2, 16000, 512, "NONE", "NONE"))
            f.writeframes(struct.pack("h" * len(audio), *audio))

            time.sleep(2)

            # Upload audio file on Amazon S3
            print("[2] Uploading audio on Amazon S3...")
            playaudio(BOOP_FILE_NAME, wait=False)
            bucket = "dianamarioawsbucket"
            session = boto3.Session(
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            )
            s3 = session.resource('s3')
            # Filename - File to upload
            # Bucket - Bucket to upload to (the top level directory under AWS S3)
            # Key - S3 object name (can contain subdirectories). If not specified then file_name is used
            s3.meta.client.upload_file(Filename='audio.wav', Bucket=bucket, Key='audio.wav')

            # Create an Amazon Transcribe job
            print("[3] Creating an Amazon Transcribe job...")        
            playaudio(BOOP_FILE_NAME, wait=False)
            result = amazon_transcribe("audio.wav", transcribe)
            print("[*] Transcribe job successfully created.\n[*] Output: " + result)
            playaudio(DING_FILE_NAME, wait=True)

            # Process text using NLTK and get answer
            answer = get_answer(result) 

            # Output voice
            print("[4] Playing answer...")
            tts = gtts.gTTS(answer)
            tts.save(ANSWER_FILE_NAME)
            playaudio(ANSWER_FILE_NAME, wait=True)
            

    finally:
        recorder.delete()

if __name__ == '__main__':
    main()
