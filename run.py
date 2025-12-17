from agents.writers.screenwriter import *
from agents.animators.animator_doubao import *
from my_a2a.card_resolver import A2ACardResolver
from a2a.server.agent_execution.context import RequestContext
import json
import os
import asyncio
from a2a.server.agent_execution.simple_request_context_builder import SimpleRequestContextBuilder
from typing import Any, Dict, List, Optional, Set, TypedDict
from my_a2a.client import A2AClient
from a2a.types import MessageSendParams
from my_a2a.protocol import build_message_request

AGENT_CARD_URL = {
    "screenwriter":"http://127.0.0.1:10007/.well-known/agent-card.json",
}

AGENT_URLS = {
    "写作":"http://127.0.0.1:10007",
    "助手":"http://127.0.0.1:10008",
}


clients: Dict[tuple[str, str], A2AClient] = {}
agent_url = AGENT_URLS

documentart_add = '''
用户的需求是创作一份纪录片的一个小片段，风格要求写实，剧情尽量平淡，重点展示用户的偏好内容
'''

def gen_documentary_script():
    print("请选择你的主题")
    theme = input()
    print("请输入内容偏好（没有则输入无）")
    preference = input()
    print("你有风格上的偏好吗（BBC风格/舌尖上的中国/其他，没有则输入无）")
    style = input()
    if style != "无":
        query = f"请创作一份关于{theme}的纪录片，偏好内容为{preference}，风格为{style}"
    else:
        query = f"请创作一份关于{theme}的纪录片，偏好内容为{preference}"
    print(f"你的需求语句为：{query}，是否调用AI生成脚本？(y/n)")
    choice = input()
    if choice == "y":
        return screenwriter.call_agent(query,documentart_add)
    else:
        print("好的，再见！")

screen_dict_link = {
    "纪录片":r'./test/video/documentary',
}

video_dict_link = {
    "纪录片":r'./test/video/documentary',
}

agent_registry = None

class AgentRegistry:
    """集中缓存各 Agent 卡片并提供基于关键词的匹配能力。"""

    def __init__(self, agent_urls: Dict[str, str]):
        self.agent_urls = agent_url
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._status: Dict[str, bool] = {}
        self._keyword_index: Dict[str, List[str]] = {}

    async def ensure_cards(self) -> Dict[str, bool]:
        """保证所有 Agent Card 已加载并返回可用性映射。"""

        if self._entries:
            return self._status

        for agent_type, base_url in self.agent_urls.items():
            # 默认认为服务不可用，只有成功拿到卡片才置为 True
            card = None
            available = False
            try:
                card = await asyncio.to_thread(self._fetch_card, base_url)
                available = True
            except Exception as exc:
                print(f"获取 {agent_type} agent card 失败: {exc}")

            entry = self._build_entry(agent_type, base_url, card)
            self._entries[agent_type] = entry
            self._status[agent_type] = available
            self._index_entry(entry)
            print(f"确认{agent_type}智能体正在待命")

        return self._status

    def _fetch_card(self, base_url: str) -> Dict[str, Any]:
        """同步读取 Agent Card，适配到线程池调用。"""

        resolver = A2ACardResolver(base_url)
        return resolver.get_agent_card()

    def _build_entry(self, agent_type: str, base_url: str, card: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """将原始卡片信息组装成内部统一结构。"""

        resolved_url = self._resolve_card_url(card, base_url)
        keywords = self._collect_keywords(agent_type, card)
        return {
            "type": agent_type,
            "card": card,
            "base_url": base_url,
            "url": resolved_url,
            "keywords": keywords,
        }

    def _index_entry(self, entry: Dict[str, Any]) -> None:
        """建立关键词到 Agent 类型的反向索引。"""

        for keyword in entry["keywords"]:
            bucket = self._keyword_index.setdefault(keyword, [])
            if entry["type"] not in bucket:
                bucket.append(entry["type"])

    def find_card(self, keyword: str) -> Optional[Dict[str, Any]]:
        """根据关键字寻找最匹配的 Agent Card。"""

        kw = keyword.lower()
        direct_matches = self._keyword_index.get(kw)
        if direct_matches:
            return self._entries.get(direct_matches[0])

        for entry in self._entries.values():
            for candidate in entry["keywords"]:
                if kw in candidate or candidate in kw:
                    return entry
        return None

    def available_agents(self) -> Dict[str, bool]:
        """返回已加载 Agent 的可用性字典。"""

        return self._status

    def all_available(self) -> bool:
        """判断所有注册 Agent 是否均已连通。"""

        return bool(self._status) and all(self._status.values())

    def _resolve_card_url(self, card: Optional[Dict[str, Any]], default_url: str) -> str:
        """优先从卡片信息中提取真实调用 URL，找不到时回退到默认地址。"""

        candidates: List[Optional[str]] = []
        if isinstance(card, dict):
            api_block = card.get("api") or card.get("apis")
            if isinstance(api_block, dict):
                for key in ("url", "base_url", "endpoint"):
                    value = api_block.get(key)
                    if isinstance(value, str):
                        candidates.append(value)
            if isinstance(card.get("links"), list):
                for item in card["links"]:
                    if isinstance(item, dict):
                        value = item.get("href") or item.get("url")
                        if isinstance(value, str):
                            candidates.append(value)
            for key in ("url", "endpoint", "baseUrl", "base_url"):
                value = card.get(key)
                if isinstance(value, str):
                    candidates.append(value)

        for candidate in candidates:
            if candidate:
                return candidate.rstrip('/')
        return default_url.rstrip('/')

    def _collect_keywords(self, agent_type: str, card: Optional[Dict[str, Any]]) -> Set[str]:
        """汇总 Agent 类型、名称、描述等字段中的关键词。"""

        keywords: Set[str] = set()
        for token in agent_type.replace("-", "_").split("_"):
            token = token.strip().lower()
            if token:
                keywords.add(token)
        keywords.add(agent_type.lower())

        if isinstance(card, dict):
            for field in ("name", "description", "summary", "title"):
                value = card.get(field)
                if isinstance(value, str):
                    keywords.update(self._tokenize(value))
            metadata = card.get("metadata")
            if isinstance(metadata, dict):
                for value in metadata.values():
                    if isinstance(value, str):
                        keywords.update(self._tokenize(value))

        return keywords

    def _tokenize(self, text: str) -> Set[str]:
        """将描述文本拆分成小写关键词集合。"""

        clean_text = text.lower().replace("-", " ").replace("_", " ")
        tokens = {token.strip() for token in clean_text.split() if token.strip()}
        return tokens

async def check_all_servers():
    """检查所有 Agent 服务是否可达，必要时提示用户手动启动。"""

    if agent_registry is None:
        raise RuntimeError("Agent registry 尚未初始化")

    print("正在检查所有代理服务器状态...")
    server_status = await agent_registry.ensure_cards()

    all_running = agent_registry.all_available()
    if not all_running:
        print("以下代理服务器可能未运行:")
        for agent, status in server_status.items():
            if not status:
                print(f"  - {agent}: {AGENT_URLS[agent]}")
        print("\n请先运行 'start_all_agents.bat' 启动所有代理服务器。")
    
    return all_running 

def create_client(agent_type: str, url: str) -> A2AClient:
    """根据 Agent 类型与目标 URL 构建或复用 A2AClient。"""

    global clients

    key = (agent_type, url)
    if key in clients:
        return clients[key]

    if not url:
        raise ValueError(f"{agent_type} 未提供有效的访问地址")

    config = {
        agent_type: {
            "url": url,
            "description": f"{agent_type} agent",
            "skills": []
        }
    }

    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    client = A2AClient(config_path)
    clients[key] = client

    os.unlink(config_path)

    return client
    
async def call_agent_with_retry(agent_keyword: str, payload, max_retries=3):
    """调用代理服务，带有重试机制，优先通过 Agent Card 解析地址。"""
    if agent_registry is None:
        raise RuntimeError("Agent registry 尚未初始化")

    entry = agent_registry.find_card(agent_keyword)
    if entry is None:
        raise ValueError(f"未找到与关键字 {agent_keyword} 匹配的代理卡片")

    agent_type = entry["type"]
    agent_url = entry["url"]
    #创建临时客户端对象与服务器通信
    client = create_client(agent_type, agent_url)
    # message = payload['params']['message']['parts'][0]['text']
    # print(message)

    for attempt in range(max_retries):
        try:
            # 通过 A2A 协议与目标代理交互
            response = await client.send_request(agent_type, payload)
            if response:
                return response
            raise Exception("未收到有效响应")
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"连接 {agent_type} 代理失败，正在重试 ({attempt+1}/{max_retries})...")
                await asyncio.sleep(2)
            else:
                print(f"无法连接到 {agent_type} 代理服务器。请确保服务器正在运行。")
                raise

def run_without_a2a():
    print("请输入你要生成的短片的类型（如纪录片、视频、动画等）")
    print("目前支持：纪录片")
    typee = input()
    if typee in screen_dict:
        print("当前存在以下剧本：")
        for idx,i in enumerate(os.listdir(screen_dict_link[typee])):
            print(f"{idx}:{i}")
        print("请输入你要使用的剧本的序号（要生成新剧本请输入-1）")
        idx = int(input())
        if idx == -1:
            script = gen_documentary_script()
        else:
            script = json.load(open(r'./test/screen/documentary/'+screen_dict[typee][idx]))
            print("你选择的剧摘要为：")
            print(script["abstract"])
        print("是否继续生成视频？(y/n)")
        choice = input()
        if choice == "y":
            animator = animator_doubao.animator(script["name"],video_dict_link[typee])
            animator.story = script
            animator.create_request(num = script["n"])
            animator.download()

def chat_with_assistant():
    while 1:
        usr_message = input("用户：")
        user_prefer_response = asyncio.run(call_agent_with_retry(
            "助手",
            usr_message,
        ))
        print(user_prefer_response)
        if "需求确认：" in user_prefer_response:
            print("assistent任务完成！获得灵感："+user_prefer_response.split("需求确认：")[1])
            break
    return user_prefer_response.split("需求确认：")[1]

def chat_with_writer(spark):
    print("这里是writer，你当前的需求为："+spark,"是否需要修改？(y/n)")
    choice = input()
    if choice == "y":
        print("请输入你要修改的内容")
        spark = input()
    return spark


def run_with_a2a():
    global agent_registry
    if agent_registry is None:
        agent_registry = AgentRegistry(AGENT_URLS)
    print("finish init")
    servers_running = asyncio.run(check_all_servers())
    print("早上好老板，今天想创作什么内容？纪录片？还是一个小动画？")
    spark = chat_with_assistant()
    spark = chat_with_writer(spark)



if __name__ == "__main__":
    run_with_a2a()