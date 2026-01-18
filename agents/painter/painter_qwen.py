from http import HTTPStatus
from urllib.parse import urlparse, unquote
from pathlib import PurePosixPath
import requests
from dashscope import ImageSynthesis
import os
import dashscope

dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'

class Painter:
    def __init__(self, name, download_link):
        self.image_urls = list()
        self.name = name
        self.download_link = f'{download_link}/{self.name}'

    def call(self, session_data):
        screen_id = session_data.get('image_generating', 0)
        prompt = session_data['material']['screen'][screen_id]
        self.image_urls.append(self.get_image_url(prompt))
        return self.download(self.image_urls[-1], idx=len(self.image_urls))

    def download(self, url, idx):
        os.makedirs(self.download_link, exist_ok=True)
        try:
            resp = requests.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            file_name = PurePosixPath(unquote(urlparse(url).path)).parts[-1]
            save_path = f"{self.download_link}/{self.name}_{idx}_{file_name}"
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"已保存：{save_path}")
            return save_path
        except Exception as e:
            print(f"下载失败 {url}：{e}")

    def get_image_url(self, prompt):
        print('please wait...')
        rsp = ImageSynthesis.call(api_key=os.getenv("DASHSCOPE_API_KEY"),
                                model="wan2.5-t2i-preview",
                                prompt=prompt,
                                n=1,
                                size='1280*1280')
        print(rsp)
        if rsp.status_code == HTTPStatus.OK:
            image_url = rsp.output.results[0].url
            print(image_url)
            return image_url
        else:
            print('Failed, status_code: %s, code: %s, message: %s' %
                (rsp.status_code, rsp.code, rsp.message))


# 测试代码示例
if __name__ == '__main__':
    # 示例session_data结构
    session_data = {
        'image_generating': 0,
        'material': {
            'screen': [
                "一间有着精致窗户的花店，漂亮的木质门，摆放着花朵"
            ]
        }
    }
    
    p = Painter(name="flower_shop", download_link="./test/images")
    p.call(session_data)
###以上是qwen文生图的工作流