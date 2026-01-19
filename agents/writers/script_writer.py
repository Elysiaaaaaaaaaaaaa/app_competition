

class ScriptWriter:
    def __init__(self, name, download_link):
        self.scripts = list()
        self.name = name
        self.download_link = f'{download_link}/{self.name}'
    
    def call(self, session_data):
        return '这里是脚本创作节点'