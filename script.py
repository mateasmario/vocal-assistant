import time
import boto3
import os
import wave
from pvrecorder import PvRecorder
import struct
import gtts
import sounddevice as sd
import soundfile as sf
from collections import Counter
from string import punctuation
import urllib.request
import json
from pydub import AudioSegment
import requests
import time
import board
import adafruit_dht
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import time as t
import json

AWS_ACCESS_KEY_ID = ""
AWS_SECRET_ACCESS_KEY = ""
ENDPOINT = ""
CLIENT_ID = "testDevice"
PATH_TO_CERTIFICATE = "certificates/8e026a2ebcd1fd2ab47a4babfecbcaea60ec9b5dac24c8a26b3073bec8a221d5-certificate.pem.crt"
PATH_TO_PRIVATE_KEY = "certificates/8e026a2ebcd1fd2ab47a4babfecbcaea60ec9b5dac24c8a26b3073bec8a221d5-private.pem.key"
PATH_TO_AMAZON_ROOT_CA_1 = "certificates/root.pem"
TOPIC = "test/testing"
RANGE = 20

questions = [
    'What\'s the room temperature?',
    'What\'s your name?',
    'Tell me a joke.',
    'Tell me a pun.',
    'Do a backflip.',
    'How many degrees are in the room?'
]

headers = {
    'Content-Type': 'application/json',
    'X-Twaip-Key': '',
}

dhtDevice = adafruit_dht.DHT22(board.D18)

ANSWER_FILE_NAME = "answer"
BOOP_FILE_NAME = "boop.wav"
DING_FILE_NAME = "ding.wav"

GENERIC_ANSWER = "I'm sorry, but I didn't understand the question. Could you please try again?"
NAME_ANSWER = "My name is Mariana."
TEMPERATURE_ANSWER = "The room temperature is "
BACKFLIP_ANSWER = "I don't think I am able to do a backflip."

def publish_iot(question, answer):
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
    mqtt_connection = mqtt_connection_builder.mtls_from_path(
            endpoint=ENDPOINT,
            cert_filepath=PATH_TO_CERTIFICATE,
            pri_key_filepath=PATH_TO_PRIVATE_KEY,
            client_bootstrap=client_bootstrap,
            ca_filepath=PATH_TO_AMAZON_ROOT_CA_1,
            client_id=CLIENT_ID,
            clean_session=False,
            keep_alive_secs=6
            )
    print("Connecting to {} with client ID '{}'...".format(
            ENDPOINT, CLIENT_ID))
    # Make the connect() call
    connect_future = mqtt_connection.connect()
    # Future.result() waits until a result is available
    connect_future.result()
    print("Connected!")
    print('Begin Publish')
        
    message = {"question" : question, "answer": answer}
    mqtt_connection.publish(topic=TOPIC, payload=json.dumps(message), qos=mqtt.QoS.AT_LEAST_ONCE)
    print("Published: '" + json.dumps(message) + "' to the topic: " + "'test/testing'")
    t.sleep(0.1)
    
    print('Publish End')
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result()

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
        data = result['TranscriptionJob']['Transcript']['TranscriptFileUri']
        urllib.request.urlretrieve(data, "data.json")

        f = open('data.json')
        json_data = json.load(f)
        return json_data['results']['transcripts'][0]['transcript']

def get_temperature():
    count = 0
    temp = 0
    
    while True:
        try:
            if count == 5:
                break
                
            temp = dhtDevice.temperature
        except RuntimeError as error:
            count+=1
            print(error.args[0])
            print("Mariana's attempts: " + str(count) + "/5")
            time.sleep(2.0)
            continue
        except Exception as error:
            dhtDevice.exit()
            raise error
        
    return str(temp)

def get_joke():
    response = requests.get("https://v2.jokeapi.dev/joke/Any")
    responseJson = response.json()
    if 'setup' in responseJson:
        return responseJson['setup'] + ' ' + responseJson['delivery']
    return responseJson['joke']

def get_pun():
    response = requests.get("https://v2.jokeapi.dev/joke/Pun")
    responseJson = response.json()
    return responseJson['setup'] + ' ' + responseJson['delivery']

def get_answer(text):
    params = {}
    params['text1'] = text
    max_similarity = 0

    best_question_index = 0

    for question_index in range(0, len(questions)):
        params['text2'] = questions[question_index]
        
        response = requests.get('https://api.twinword.com/api/text/similarity/latest/', headers=headers, params=params)
        responseJson = response.json()
        
        curr_similarity = responseJson['similarity']
        if curr_similarity > max_similarity:
            max_similarity = curr_similarity
            best_question_index = question_index
            
    if max_similarity <= 0.6:
        return GENERIC_ANSWER
    else:
        if best_question_index == 0:
            return TEMPERATURE_ANSWER + ' ' + get_temperature()
        elif best_question_index == 1:
            return NAME_ANSWER
        elif best_question_index == 2:
            return get_joke()
        elif best_question_index == 3:
            return get_pun()
        elif best_question_index == 4:
            return BACKFLIP_ANSWER
        elif best_question_index == 5:
            return TEMPERATURE_ANSWER + ' ' + get_temperature()

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
            f.setparams((1, 2, 16000, 512, "NONE", "NONE"))
            f.writeframes(struct.pack("h" * len(audio), *audio))

            time.sleep(2)

            # Upload audio file on Amazon S3
            print("[2] Uploading audio on Amazon S3...")
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
            result = amazon_transcribe("audio.wav", transcribe)
            print("[*] Transcribe job successfully created.\n[*] Output: " + result)

            # Process text using NLTK and get answer
            answer = get_answer(result) 

            # Output voice
            print("[4] Playing answer...")
            tts = gtts.gTTS(answer)
            tts.save(ANSWER_FILE_NAME + ".mp3")
            
            # assign files
            input_file = "answer.mp3"
            output_file = "answer.wav"
              
            # convert mp3 file to wav file
            sound = AudioSegment.from_mp3(input_file)
            sound.export(output_file, format="wav")
            
            playaudio(ANSWER_FILE_NAME + ".wav", wait=True)
            
            publish_iot(result, answer)
            

    finally:
        recorder.delete()

if __name__ == '__main__':
    main()

