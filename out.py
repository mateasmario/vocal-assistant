import gtts
import sounddevice as sd
import soundfile as sf


tts = gtts.gTTS("Hello, dear user!")
tts.save("answer.wav")


filename = 'answer.wav'
# Extract data and sampling rate from file
data, fs = sf.read(filename, dtype='float32')  
sd.play(data, fs)
status = sd.wait()  # Wait until file is done playing