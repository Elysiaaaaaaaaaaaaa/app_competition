import json
import httpx
from typing import Dict, Any
from termcolor import colored

class A2ACardResolver:
    """
    A2A Agent Card 解析器，负责从A2A服务器获取Agent卡片信息
    """
    def __init__(self, base_url, agent_card_path='/.well-known/agent.json'):
        self.base_url = base_url.rstrip('/')
        self.agent_card_path = agent_card_path.lstrip('/')

    def get_agent_card(self) -> Dict[str, Any]:
        """
        同步获取Agent卡片信息
        
        Returns:
            Dict[str, Any]: Agent卡片信息的字典表示
        """
        with httpx.Client(timeout=10.0) as client:
            try:
                response = client.get(f"{self.base_url}/{self.agent_card_path}")
                response.raise_for_status()
                return response.json()
            except json.JSONDecodeError as e:
                print(colored(f"解析Agent卡片JSON时出错: {str(e)}", "red"))
                raise Exception(f"解析Agent卡片JSON时出错: {str(e)}") from e
            except httpx.HTTPError as e:
                print(colored(f"HTTP错误: {str(e)}", "red"))
                raise Exception(f"获取Agent卡片时出错: {str(e)}") from e
            except Exception as e:
                print(colored(f"获取Agent卡片时出错: {str(e)}", "red"))
                raise
