import pandas as pd
import time
import boto3
import os
import wave
from pvrecorder import PvRecorder
import struct

AWS_ACCESS_KEY_ID = ""
AWS_SECRET_ACCESS_KEY = ""

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
            print("Saving audio file on local drive...")
            f.setparams((1, 2, 16000, 512, "NONE", "NONE"))
            f.writeframes(struct.pack("h" * len(audio), *audio))

            time.sleep(2)

            # Upload audio file on Amazon S3
            print("Uploading audio on Amazon S3...")
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
            print("Creating an Amazon Transcribe job...")
            result = amazon_transcribe("audio.wav", transcribe)
            print(result)

    finally:
        recorder.delete()

if __name__ == '__main__':
    main()
