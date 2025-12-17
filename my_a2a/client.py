import json
import asyncio
from typing import Dict, List, Any, Optional
from termcolor import colored
import httpx
from a2a.client.helpers import create_text_message_object
from .card_resolver import A2ACardResolver
from .protocol import build_message_request, build_task_request, DEFAULT_TIMEOUT, LONG_TIMEOUT, MAX_POLL_ATTEMPTS, DEFAULT_POLL_INTERVAL, MAX_RETRIES

def load_servers_config(config_path: str) -> Dict[str, Dict[str, Any]]:
    """从配置文件加载服务器配置"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(colored(f"加载服务器配置失败: {str(e)}", "red"))
        return {}

class A2AClient:
    """
    A2A客户端类，用于与A2A服务器通信
    
    该客户端实现了A2A JSON-RPC协议，提供消息发送和任务查询功能。
    简化版本，专注于发送请求和接收回复的核心功能。
    """
    
    def __init__(self, config_path: str):
        """
        初始化A2A客户端
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.servers_config = load_servers_config(config_path)
        self.server_names = list(self.servers_config.keys())
        self.clients = {}  # 存储各服务器对应的URL和信息
        
        # 初始化客户端连接
        self._init_clients()
    
    def _init_clients(self):
        """同步初始化所有的A2A客户端"""
        for name, config in self.servers_config.items():
            url = config.get('url')
            if not url:
                print(colored(f"警告: 服务器 {name} 未配置URL，将被跳过", "yellow"))
                continue
            
            try:
                # 使用同步方法获取agent_card
                card_resolver = A2ACardResolver(url)
                try:
                    print(colored(f"正在连接服务器: {name} ({url})", "blue"))
                    agent_card = card_resolver.get_agent_card()
                    
                    # 存储服务器信息
                    self.clients[name] = {
                        "url": url,
                        "agent_card": agent_card
                    }
                    print(colored(f"已成功连接到A2A服务器: {name}", "green"))
                except Exception as e:
                    print(colored(f"获取agent_card时出错: {str(e)}", "red"))
                    # 即使获取卡片失败，也记录URL以允许发送请求
                    self.clients[name] = {
                        "url": url,
                        "agent_card": {}
                    }
                
            except Exception as e:
                print(colored(f"初始化客户端 {name} 时出错: {str(e)}", "red"))
    
    async def send_request(self, server_name: str, message: str) -> Optional[str]:
        """
        向指定的服务器发送请求
        
        Args:
            server_name: 服务器名称
            message: 请求消息
            
        Returns:
            Optional[str]: 服务器响应，如果出错则返回None
        """
        if server_name not in self.servers_config:
            print(colored(f"错误: 未找到名为 {server_name} 的服务器", "red"))
            return None
            
        if server_name not in self.clients:
            print(colored(f"错误: 服务器 {server_name} 未成功初始化", "red"))
            return None
        
        server_info = self.clients[server_name]
        server_url = server_info["url"]
        
        print(colored(f"\n正在向 {server_name} 发送请求...", "cyan"))
        
        try:
            message_dict = build_message_request(message)
            #print(message_dict)
            
            try:
                async with httpx.AsyncClient(timeout=LONG_TIMEOUT) as client:
                    response = await client.post(
                        f"{server_url}/",
                        json=message_dict,
                        headers={"Content-Type": "application/json"}
                    )
                    response.raise_for_status()
                    response_data = response.json()
                    #print(colored(f"请求已发送，响应: {json.dumps(response_data, indent=2)}", "blue"))
                    
                    # 检查响应中是否包含完整的结果
                    text_content = self._extract_text_from_response(response_data)
                    if text_content:
                        return text_content
                        
            except httpx.ReadTimeout:
                print(colored("请求发送超时，但服务器可能仍在处理。尝试获取任务状态...", "yellow"))
                # 从请求数据中获取可能的任务ID
                task_id = request_data["params"]["message"]["contextId"]
                print(colored(f"使用备用任务ID: {task_id}", "yellow"))
                
                task_result = await self._poll_task_status(server_url, task_id, max_retries=5)
                if task_result:
                    return task_result
                else:
                    print(colored("无法确认请求是否被服务器处理。请稍后重试。", "red"))
                    return None
            except Exception as e:
                print(colored(f"HTTP请求出错: {str(e)}", "red"))
                import traceback
                traceback.print_exc()
                return None
            
            # 如果没有直接返回结果，并且成功获取了响应数据，继续处理
            if response_data is None:
                return None
            # 检查响应中是否有错误
            if "error" in response_data:
                error_msg = response_data["error"].get("message", "未知错误")
                print(colored(f"错误: {error_msg}", "red"))
                return None
            
            # 获取任务ID
            result = response_data.get("result", {})
            # 检查是否有状态字段，如果有且为completed，说明响应中已包含结果
            if "status" in result and isinstance(result["status"], dict) and result["status"].get("state") == "completed":
                print(colored("任务已完成，直接从响应中提取结果", "green"))
                # 从响应中提取结果
                artifacts = result.get("artifacts", [])
                if artifacts:
                    for artifact in artifacts:
                        parts = artifact.get("parts", [])
                        for part in parts:
                            if "text" in part:
                                return part["text"]
                print(colored("在完成的任务中未找到文本内容", "yellow"))
                return None
            
            task_id = result.get("taskId")
            if not task_id:
                # 尝试从result.id获取任务ID
                task_id = result.get("id")
                if not task_id:
                    print(colored("错误: 服务器未返回任务ID", "red"))
                    return None
                print(colored(f"从result.id字段获取到任务ID: {task_id}", "blue"))
            
            # 轮询任务状态
            task_result = await self._poll_task_status(server_url, task_id)
            
            # 处理任务结果
            if task_result:
                return task_result
            else:
                print(colored("无法获取有效的任务结果。请稍后重试。", "red"))
                return None
                
        except Exception as e:
            print(colored(f"发送请求时出错: {str(e)}", "red"))
            import traceback
            traceback.print_exc()
            return None
    
    async def _poll_task_status(self, server_url: str, task_id: str, max_attempts: int = MAX_POLL_ATTEMPTS, 
                               interval: float = DEFAULT_POLL_INTERVAL, max_retries: int = MAX_RETRIES) -> Optional[str]:
        """
        轮询任务状态，带有重试机制
        
        Args:
            server_url: 服务器URL
            task_id: 任务ID
            max_attempts: 最大尝试次数
            interval: 轮询间隔（秒）
            max_retries: 单次请求的最大重试次数
            
        Returns:
            Optional[str]: 任务结果，如果超时或出错则返回None
        """
        print(colored("等待服务器处理请求", "cyan"), end="")
        
        for attempt in range(max_attempts):
            # 显示进度百分比以提供更好的反馈
            progress = min(100, int((attempt / max_attempts) * 100))
            if attempt % 5 == 0:  # 每5次更新一次进度显示
                print(colored(f"\n等待中... {progress}% ({attempt}/{max_attempts})", "cyan"), end="")
            else:
                print(colored(".", "cyan"), end="", flush=True)
            
            # 构建获取任务状态的请求
            request_data = build_task_request(task_id)
            
            # 实现重试逻辑
            retry_count = 0
            while retry_count <= max_retries:
                try:
                    # 使用更长的超时时间
                    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                        response = await client.post(
                            f"{server_url}/",
                            json=request_data,
                            headers={"Content-Type": "application/json"}
                        )
                        response.raise_for_status()
                        response_data = response.json()
                    
                    # 处理响应数据
                    if "error" in response_data:
                        error_msg = response_data["error"].get("message", "未知错误")
                        if "not found" in error_msg.lower() or "not exist" in error_msg.lower():
                            if retry_count == max_retries:
                                print(colored(f"\n任务ID {task_id} 暂未创建，继续等待...", "yellow"))
                                break
                            retry_count += 1
                            await asyncio.sleep(1)
                            continue
                        else:
                            print(colored(f"\n错误: {error_msg}", "red"))
                            return None
                    
                    # 重置重试计数器
                    retry_count = 0
                    
                    # 获取任务状态
                    result = response_data.get("result", {})
                    status = result.get("status", {}).get("state")
                    
                    # 任务完成
                    if status == "completed":
                        print(colored("\n响应已收到! ✓", "green", attrs=["bold"]))
                        
                        # 从结果中提取文本
                        artifacts = result.get("artifacts", [])
                        text_content = self._extract_text_from_artifacts(artifacts)
                        if text_content:
                            return text_content
                            
                        # 尝试其他可能的文本位置
                        if "output" in result:
                            if isinstance(result["output"], str):
                                return result["output"]
                            elif isinstance(result["output"], dict) and "text" in result["output"]:
                                return result["output"]["text"]
                        
                        print(colored("未在响应中找到文本内容", "yellow"))
                        return None
                    
                    # 任务失败
                    elif status == "failed":
                        print(colored("\n错误: 任务执行失败", "red"))
                        error_info = result.get("error", {})
                        if error_info:
                            print(colored(f"错误详情: {json.dumps(error_info, indent=2)}", "red"))
                        return None
                    
                    # 任务正在运行
                    elif status == "running":
                        print(colored("(运行中)", "green"), end="", flush=True)
                        break
                    
                    # 其他状态
                    break
                
                except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                    if retry_count == max_retries:
                        print(colored(f"\n第{retry_count+1}次尝试获取任务状态超时", "yellow"))
                        break
                    retry_count += 1
                    print(colored("r", "yellow"), end="", flush=True)
                    continue
                
                except Exception as e:
                    if retry_count == max_retries:
                        print(colored(f"\n轮询任务状态时出错: {str(e)}", "red"))
                        break
                    retry_count += 1
                    continue
            
            # 等待间隔时间后继续下一次轮询
            await asyncio.sleep(interval)
        
        print(colored("\n警告: 等待任务完成超时，请检查服务器状态", "yellow"))
        return None
    
    def _extract_text_from_response(self, response_data: Dict[str, Any]) -> Optional[str]:
        """从响应中提取文本内容"""
        if "result" in response_data and "artifacts" in response_data["result"]:
            print(colored("检测到响应中包含完整结果，直接提取文本内容", "green"))
            return self._extract_text_from_artifacts(response_data["result"]["artifacts"])
        return None
        
    def _extract_text_from_artifacts(self, artifacts: List[Dict[str, Any]]) -> Optional[str]:
        """从任务结果的artifacts中提取文本内容"""
        if not artifacts:
            return None
            
        for artifact in artifacts:
            if "parts" in artifact and artifact["parts"]:
                for part in artifact["parts"]:
                    if "text" in part and part["text"]:
                        return part["text"]
        
        print(colored("未找到文本内容", "yellow"))
        return None