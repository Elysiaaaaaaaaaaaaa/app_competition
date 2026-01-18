import requests
import json

# 测试API端点
url = "http://localhost:8003/api/v1/work"
headers = {"Content-Type": "application/json"}
data = {
    "project_name": "test_project",
    "user_input": "测试请求",
    "user_id": "test_user"
}

print("发送请求到API端点...")
print(f"URL: {url}")
print(f"Headers: {headers}")
print(f"Data: {data}")

try:
    response = requests.post(url, headers=headers, data=json.dumps(data))
    print(f"\n响应状态码: {response.status_code}")
    print(f"响应内容: {response.text}")
    
    # 尝试解析JSON响应
    try:
        response_json = response.json()
        print(f"解析后的JSON响应: {json.dumps(response_json, indent=4, ensure_ascii=False)}")
    except json.JSONDecodeError:
        print("无法解析JSON响应")
        
except Exception as e:
    print(f"发送请求时发生错误: {e}")