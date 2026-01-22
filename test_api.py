import requests
import json

# 测试API端点的基础URL
base_url = "http://localhost:8003"
headers = {"Content-Type": "application/json"}

# 测试用的用户ID
test_user_id = "test_user"

def test_work_api():
    """测试work API端点"""
    url = f"{base_url}/api/v1/work"
    data = {
        "project_name": "test_project",
        "user_input": "测试请求",
        "user_id": test_user_id,
        "mode": "test"
    }

    print("\n=== 测试 /api/v1/work API ===")
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

def test_get_projects_api():
    """测试获取用户项目列表API端点"""
    url = f"{base_url}/api/v1/projects/list"
    data = {
        "user_id": test_user_id
    }

    print("\n=== 测试 /api/v1/projects/list API ===")
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

def test_get_project_history_api():
    """测试获取指定项目对话历史API端点"""
    url = f"{base_url}/api/v1/projects/history"
    data = {
        "user_id": test_user_id,
        "project_name": "test_project"
    }

    print("\n=== 测试 /api/v1/projects/history API ===")
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

def test_create_project_api():
    """测试新建项目API端点"""
    url = f"{base_url}/api/v1/projects/new"
    data = {
        "user_id": test_user_id,
        "project_name": "new_test_project",
        "workflow_type": "text2video"
    }

    print("\n=== 测试 /api/v1/projects/new API ===")
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

if __name__ == "__main__":
    print("开始测试API端点...")
    
    # 测试各个API端点
    test_work_api()
    test_get_projects_api()
    test_create_project_api()
    test_get_project_history_api()
    
    print("\n所有API测试完成!")