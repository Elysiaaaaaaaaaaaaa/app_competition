import os
import time
import json
# 通过 pip install 'volcengine-python-sdk[ark]' 安装方舟SDK
from volcenginesdkarkruntime import Ark
from agents.writers.screenwriter import *
import requests

# 请确保您已将 API Key 存储在环境变量 ARK_API_KEY 中
# 初始化Ark客户端，从环境变量中读取您的API Key
client = Ark(
    # 此为默认路径，您可根据业务所在地域进行配置
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    # 从环境变量中获取您的 API Key。此为默认方式，您可根据需要进行修改
    api_key="c96dbd1f-aeab-461c-90d6-8096b0baeecd",
)

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
            if cnt>=num:
                break
            video_link = f"{self.download_link}/{self.name}_{cnt}.mp4"
            if os.path.exists(video_link):
                print("视频已存在，跳过创建请求")
                cnt+=1
                continue
            create_result = client.content_generation.tasks.create(
                model="doubao-seedance-1-0-pro-fast-251015",  # 模型 Model ID 已为您填入
                content=[
                    {
                        # 文本提示词与参数组合
                        "type": "text",
                        "text": f"{outline}  --resolution 720p  --duration 6 --camerafixed false --watermark true"
                    }
                ]
            )
            print("----- polling task status -----")
            task_id = create_result.id
            while True:
                get_result = client.content_generation.tasks.get(task_id=task_id)
                status = get_result.status
                if status == "succeeded":
                    print("----- task succeeded -----")
                    print(get_result)
                    self.video_url.append(get_result.content.video_url)
                    break
                elif status == "failed":
                    print("----- task failed -----")
                    print(f"Error: {get_result.error}")
                    break
                else:
                    print(f"Current status: {status}, Retrying after 3 seconds...")
                    time.sleep(3)
            cnt+=1

if __name__ == "__main__":
    a = animator("monalisa")
    query = ""
    a.get_story(query=query,link = r'./test/screen/monalisa.json')
    a.create_request(num=1)
    a.download()

    # print("----- create request -----")
    # create_result = client.content_generation.tasks.create(
    #     model="doubao-seedance-1-0-pro-250528", # 模型 Model ID 已为您填入
    #     content=[
    #         {
    #             # 文本提示词与参数组合
    #             "type": "text",
    #             "text": "无人机以极快速度穿越复杂障碍或自然奇观，带来沉浸式飞行体验  --resolution 1080p  --duration 5 --camerafixed false --watermark true"
    #         },
    #         { # 若仅需使用文本生成视频功能，可对该大括号内的内容进行注释处理，并删除上一行中大括号后的逗号。
    #             # 首帧图片URL
    #             "type": "image_url",
    #             "image_url": {
    #                 "url": "https://ark-project.tos-cn-beijing.volces.com/doc_image/seepro_i2v.png"
    #             }
    #         }
    #     ]
    # )
    # print(create_result)
    #
    # # 轮询查询部分
    # print("----- polling task status -----")
    # task_id = create_result.id
    # while True:
    #     get_result = client.content_generation.tasks.get(task_id=task_id)
    #     status = get_result.status
    #     if status == "succeeded":
    #         print("----- task succeeded -----")
    #         print(get_result)
    #         break
    #     elif status == "failed":
    #         print("----- task failed -----")
    #         print(f"Error: {get_result.error}")
    #         break
    #     else:
    #         print(f"Current status: {status}, Retrying after 3 seconds...")
    #         time.sleep(3)
