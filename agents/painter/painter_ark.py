import os 
from volcenginesdkarkruntime import Ark
import json

client = Ark( 
    # 此为默认路径，您可根据业务所在地域进行配置 
    base_url="https://ark.cn-beijing.volces.com/api/v3", 
    # 从环境变量中获取您的 API Key。此为默认方式，您可根据需要进行修改 
    api_key="c96dbd1f-aeab-461c-90d6-8096b0baeecd", 
) 

def paint(prompt):
    imagesResponse = client.images.generate(
        model="doubao-seedream-4-0-250828", 
        prompt=prompt,
        size="2K",
        response_format="url",
        watermark=False,
        sequential_image_generation = "disabled"
    ) 
    return imagesResponse.data[0].url

if __name__ == "__main__":
    data = json.load(open("./test/screen/monalisa.json",encoding='utf-8'))
    prompt = data["outline"][0]
    url = paint(prompt)
    print(url)