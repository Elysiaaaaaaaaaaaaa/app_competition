from elevenlabs import save,client
from elevenlabs import ElevenLabs

base_link = r'./audio/sound_test/'
voice_id = "JBFqnCBsd6RMkjVDRZzb"  
voice_name = 'Ceorge'
elevenlabs = ElevenLabs(
  api_key="1593ccdbb764d07d00ae4266f6d923a6395bea37f93857e32fac2235e03b1890",
)
audio = elevenlabs.text_to_speech.convert(
    text="The first move is what sets everything in motion.",
    voice_id=voice_id,
    model_id="eleven_multilingual_v2",
    output_format="mp3_44100_128",
)
# 保存音频到本地文件
save(audio, filename=f'{voice_id}_{voice_name}.mp3')
# 播放音频
class AudioPlayer:
    def __init__(self, audio_file):
        self.audio_file = audio_file
    def play(self):
        from elevenlabs import play
        play(self.audio_file)