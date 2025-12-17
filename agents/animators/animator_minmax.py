import replicate
import json
import os

# 设置Replicate API令牌
os.environ['REPLICATE_API_TOKEN'] = 'r8_64l0mizCpOiB2Jd6Y8mftGHKvt1p91L2k6B68'

data = json.load(open(r'./test/screen/monalisa.json', encoding='utf-8'))
inpu = {
    "prompt": data["script"][0]
}

output = replicate.run(
    "minimax/video-01",
    input=inpu
)

# 直接打印输出的URL
print(output)
#=> "https://replicate.delivery/.../output.mp4"

# To write the file to disk:
# with open("output.mp4", "wb") as file:
#     file.write(output.read())

#=> output.mp4 written to disk