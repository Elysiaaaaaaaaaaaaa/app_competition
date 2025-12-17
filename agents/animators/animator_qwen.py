from http import HTTPStatus
from dashscope import VideoSynthesis
import dashscope
import json
import os
import requests

dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
dashscope.api_key = os.getenv('A_LI_MODULE_API')

class animator:
    def __init__(self,name,download_link):
        self.story = dict()
        self.video_url = list()
        self.name = name
        self.download_link = download_link+f'/{self.name}'

    def get_story(self,query,link = None):
        if link:
            print("正在加载大纲文件："+link)
            with open(link,"r",encoding='utf-8') as f:
                self.story = json.load(f)
        else:
            print("没有提供大纲文件，使用screenwriter生成大纲")
            writer = screenwriter.Script(query=query,name = self.name)
            self.story = writer.data
        return self.story

    def download(self):
        os.makedirs(self.download_link, exist_ok=True)
        for idx, url in enumerate(self.video_url):
            try:
                resp = requests.get(url, stream=True, timeout=30)
                resp.raise_for_status()
                save_path = f"{self.download_link}/{self.name}_{idx + 1}.mp4"
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                print(f"已保存：{save_path}")
            except Exception as e:
                print(f"下载失败 {url}：{e}")
    
    def create_request(self,num = 0):
        cnt = 1
        for outline in self.story["script"]:
            if cnt>num:
                break
            video_link = f"{self.download_link}/{self.name}_{cnt}.mp4"
            if os.path.exists(video_link):
                print("视频已存在，跳过创建请求")
                cnt+=1
                continue
            url = get_video_url(outline)
            self.video_url.append(url)
            cnt+=1

def get_video_url(prompt):
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
