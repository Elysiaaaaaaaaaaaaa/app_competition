from http import HTTPStatus
from dashscope import VideoSynthesis
import dashscope
import json
import os
import requests

dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
dashscope.api_key = "sk-8c9152365e554289834e30d12885ec03"

class Animator:
    def __init__(self,name,download_link):
        self.video_url = list()
        self.name = name
        self.download_link = download_link+f'/{self.name}'

    def call(self,session_data):
        screen_id = session_data['video_generating']
        prompt = session_data['material']['screen'][screen_id]
        self.video_url.append(self.get_video_url(prompt))
        return self.download(self.video_url[-1],idx = len(self.video_url))

    def download(self,url,idx):
        os.makedirs(self.download_link, exist_ok=True)
        try:
            resp = requests.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            save_path = f"{self.download_link}/{self.name}_{idx}.mp4"
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"已保存：{save_path}")
            return save_path
        except Exception as e:
            print(f"下载失败 {url}：{e}")

    def get_video_url(self,prompt):
        # call sync api, will return the result
        print('please wait...')
        rsp = VideoSynthesis.call(model='wan2.5-t2v-preview',
                                prompt=prompt,
                                size='832*480',
                                duration = 5)
        print(rsp)
        if rsp.status_code == HTTPStatus.OK:
            print(rsp.output.video_url)
            return rsp.output.video_url
        else:
            print('Failed, status_code: %s, code: %s, message: %s' %
                (rsp.status_code, rsp.code, rsp.message))


if __name__ == '__main__':
    a = animator(name = "western_food",download_link = r'./test/video/documentary')
    a.get_story(query = "",link = r'./test/screen/documentary/western_food.json')
    a.create_request(num = 1)
    a.download()
