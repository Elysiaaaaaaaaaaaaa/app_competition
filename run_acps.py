from __future__ import annotations
import re
import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, TypedDict
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

_CURRENT_DIR = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.abspath(_CURRENT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from base import get_agent_logger
from transform_ import to_json, from_json
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from agents.assistant.director_assistant import Assistant
from acps_aip.aip_rpc_client import AipRpcClient
from acps_aip.aip_base_model import Task, TextDataItem
from acps_aip.discovery_client import DiscoveryError, discover_agent_endpoints
from acps_aip.mtls_config import load_mtls_config_from_json

import json

from file_manage import UserFile
from agents.writers.screenwriter import ScreenWriter
from agents.assistant.director_assistant import Assistant
from agents.writers.outline_writer import OutlineWriter
from agents.animators.animator_qwen_t2v import Animator

from tools.merge_video import merge_videos
class AgentEntry(TypedDict):
    """缓存单个 Agent 基础信息与预处理关键字。"""

    name: str
    client: AipRpcClient
    keywords: Set[str]
    url: str

def _resolve_discovery_timeout(default: float = 10.0) -> float:
    """读取发现服务超时配置，支持多个环境变量名称。"""

    for key in ("PERSONAL_ASSISTANT_DISCOVERY_TIMEOUT", "DISCOVERY_TIMEOUT"):
        raw_value = os.getenv(key)
        if raw_value:
            try:
                return float(raw_value)
            except ValueError:
                break
    return default

@dataclass
class AssistantReply:
    text: str
    awaiting_followup: bool = True
    end_session: bool = False

AGENT_KEYWORD_ALIASES: Dict[str, Set[str]] = {
    "outline_writer": {"写作", "分镜大纲", "大纲"},
}
LEADER_AGENT_ID = "director_assistant"
DISCOVERY_TIMEOUT = _resolve_discovery_timeout()
CLIENT_CONFIG_JSON = r"./agents/writers/outline_writer.json"
DISCOVERY_BASE_URL = "https://www.ioa.pub/discovery/api/discovery/"
AGENT_DISCOVERY_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "outline_writer": {
        "query": "分镜大纲",
        "limit": 1,
    },
}

REQUIRED_AGENT_KEYS: List[str] = list(AGENT_DISCOVERY_DEFAULTS.keys())

# 用户在 CLI 中可用于立即退出的指令集合。
EXIT_COMMANDS = {"退出", "再见", "bye", "quit", "exit", "结束"}

class AgentRegistry:
    """集中管理 Agent 关键字映射，支持通过中文/英文关键词检索。"""

    def __init__(self, clients: Dict[str, AipRpcClient], aliases: Dict[str, Set[str]]):
        """初始化关键字索引与缓存。

        Args:
            clients: 名称到 RPC 客户端的映射。
            aliases: 各 Agent 的额外别名集合。
        """
        self._entries: Dict[str, AgentEntry] = {}
        self._keyword_index: Dict[str, str] = {}

        for name, client in clients.items():
            keywords = self._collect_keywords(name, aliases.get(name, set()))
            entry: AgentEntry = {
                "name": name,
                "client": client,
                "keywords": keywords,
                "url": getattr(client, "partner_url", ""),
            }
            self._entries[name] = entry
            for kw in keywords:
                normalized = self._normalize(kw)
                if normalized:
                    self._keyword_index[normalized] = name

    @staticmethod
    def _normalize(keyword: str) -> str:
        """剥离多余空白并转小写，便于构建统一索引。"""
        return keyword.strip().lower()

    def _collect_keywords(self, name: str, extra: Set[str]) -> Set[str]:
        """提取默认英文别名并融合额外中文关键词。

        Args:
            name: Agent 注册名，通常为英文。
            extra: 业务提供的扩展别名集合。

        Returns:
            包含大小写、拆分 token 在内的关键词集合。
        """
        tokens: Set[str] = set()
        canonical = name.strip().lower()
        if canonical:
            tokens.add(name)
            tokens.add(canonical)
            for part in canonical.replace("-", " ").replace("_", " ").split():
                if part:
                    tokens.add(part)

        for item in extra:
            cleaned = item.strip()
            if cleaned:
                tokens.add(cleaned)
                tokens.add(cleaned.lower())

        return tokens

    def find(self, keyword: str) -> Optional[AgentEntry]:
        """根据输入关键字检索 Agent 描述。

        Args:
            keyword: 用户输入或内部定义的触发词。

        Returns:
            若命中则返回 AgentEntry，否则 ``None``。
        """
        normalized = self._normalize(keyword)
        direct = self._keyword_index.get(normalized)
        if direct:
            return self._entries.get(direct)

        for entry in self._entries.values():
            for candidate in entry["keywords"]:
                norm_candidate = self._normalize(candidate)
                if normalized and (normalized in norm_candidate or norm_candidate in normalized):
                    return entry
        return None

    def available_agents(self) -> Dict[str, bool]:
        """返回所有已缓存 Agent 的可用性映射，辅助调试展示。"""
        return {name: True for name in self._entries}

class ChatGraphState(TypedDict, total=False):
    """LangGraph 节点之间流转的对话状态。"""

    session_id: str
    user_input: str
    session_data: Dict[str, Any]
    reply: List[AssistantReply]

CONFIRM_TEXT = set(["确认","是","确定","好的"])

logger = get_agent_logger(
    "client.personal_assistant", "PERSONAL_ASSISTANT_CLIENT_LOG_LEVEL", "INFO"
)


def _extract_text_from_task(task: Task) -> Optional[str]:
    """从任务对象中提取最新一条文本结果。

    遍历顺序遵循「任务状态 dataItems > 历史消息 dataItems」，一旦获取
    `TextDataItem` 即返回，若未找到则返回 ``None``，交由调用方决定如何处理。

    Args:
        task: RPC 返回的任务对象。

    Returns:
        提取出的文本字符串或 ``None``。
    """
    data_items = getattr(task.status, "dataItems", None) or []
    for item in data_items:
        if isinstance(item, TextDataItem):
            return item.text
    history = getattr(task, "messageHistory", None) or []
    for message in reversed(history):
        data = getattr(message, "dataItems", None) or []
        for item in data:
            if isinstance(item, TextDataItem):
                return item.text
    return None

def _build_discovery_headers() -> Optional[Dict[str, str]]:
    """根据环境变量构造发现服务请求所需的 HTTP 头。"""

    headers: Dict[str, str] = {}
    return headers or None


def _build_discovery_config() -> Dict[str, Dict[str, Any]]:
    """结合默认值与环境变量，生成传给发现服务的查询配置。"""

    config: Dict[str, Dict[str, Any]] = {}
    for name, defaults in AGENT_DISCOVERY_DEFAULTS.items():
        prefix = name.upper()
        query = os.getenv(f"{prefix}_DISCOVERY_QUERY", defaults.get("query", "")).strip()
        if not query:
            raise RuntimeError(f"未配置 {name} 的发现查询词")

        limit = defaults.get("limit", 1)
        limit_override = os.getenv(f"{prefix}_DISCOVERY_LIMIT")
        if limit_override:
            try:
                limit = int(limit_override)
            except ValueError:
                logger.warning(
                    "invalid_discovery_limit name=%s value=%s", name, limit_override
                )

        config[name] = {
            "query": query,
            "limit": limit,
        }
    return config

async def _initialize_clients_via_discovery(
    ssl_context
) -> Dict[str, AipRpcClient]:
    """调用发现服务并初始化所有必需的 Agent 客户端。"""

    if not DISCOVERY_BASE_URL:
        raise RuntimeError("PERSONAL_ASSISTANT_DISCOVERY_URL 未配置")

    config = _build_discovery_config()
    headers = _build_discovery_headers()
    request_summary = [
        {
            "name": name,
            "query": cfg["query"],
            "limit": cfg.get("limit"),
        }
        for name, cfg in config.items()
    ]
    logger.info(
        "event=discovery_request base_url=%s agents=%s",
        DISCOVERY_BASE_URL,
        request_summary,
    )
    try:
        endpoints = await discover_agent_endpoints(
            DISCOVERY_BASE_URL,
            config,
            timeout=DISCOVERY_TIMEOUT,
            headers=headers,
        )
    except DiscoveryError as exc:
        raise RuntimeError(f"Agent 发现失败: {exc}") from exc

    for name in REQUIRED_AGENT_KEYS:
        if name in endpoints:
            cfg = config.get(name, {})
            endpoint = endpoints[name]
            logger.info(
                "event=discovery_response agent=%s query=%s url=%s",
                name,
                cfg.get("query"),
                endpoint.endpoint_url,
            )

    missing = [name for name in REQUIRED_AGENT_KEYS if name not in endpoints]
    if missing:
        raise RuntimeError("发现结果缺少以下 Agent: " + ", ".join(missing))

    clients: Dict[str, AipRpcClient] = {}
    for name in REQUIRED_AGENT_KEYS:
        endpoint = endpoints[name]
        clients[name] = AipRpcClient(
            partner_url=endpoint.endpoint_url,
            leader_id=LEADER_AGENT_ID,
            ssl_context=ssl_context,
        )
    return clients

def extract_idea(ai_single_reply):
    """
    从AI的单次回复中提取「当前我们的想法」相关内容
    :param ai_single_reply: AI的单次回复字符串（一句/一段）
    :return: 提取到的内容列表（无匹配则返回空列表）
    """
    # 定义关键词（包含两种相关表述）
    keywords_pattern = r"当前我们(?:的想法|还没有确认具体想法)[^？\n]*"
    # 从单次回复中匹配目标内容
    extracted_content = re.findall(keywords_pattern, ai_single_reply)
    # 整理结果，去除空字符串并去重
    result = [content.strip() for content in extracted_content if content.strip()]
    
    return result

class PersonalAssistantOrchestrator:
    def __init__(self, clients: Dict[str, AipRpcClient],userfile:UserFile,project_name:str,mode:str):
        #self.clients = clients
        self.userfile = userfile
        self.project_name = project_name
        if self.project_name not in self.userfile.user_project:
            self.project_name = self.userfile.init_project(self.project_name)
            self.main_session_id = f"session-{uuid.uuid4()}"
        else:
            self.main_session_id = self.userfile.project_content[self.project_name]['session_id']
        
        self.mode = mode
        logger.info("event=cli_start session_id=%s user=%s", self.main_session_id,self.userfile.user)
        # 关键字注册表：支持用自然语言别名查找底层客户端。
        #self.registry = AgentRegistry(clients, AGENT_KEYWORD_ALIASES)
        self._history_store: Dict[str, List[AIMessage | HumanMessage | SystemMessage]] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}##会话记录加载到这里
        self._sessions = self.userfile.load_session()

        self.outline = None
        self.screen = []
        self.abstract = None
        self.assistant = Assistant()
        self.outline_writer = OutlineWriter()
        self.screen_writer = ScreenWriter()
    
        self.animator = Animator(name=self.project_name,download_link=self.userfile.project_path)
        
    # 构建 LangGraph 状态图，节点集合与 a2a 版本保持一致（intent/confirm/workflow/chat/decline）。
        self._graph = self._build_graph()

    async def acps_call_agent(self, keyword: str, payload: str, session_id: str) -> str:
        """根据关键词解析对应 Agent 并发起 RPC 调用。

        Args:
            keyword: 触发的 Agent 别名。
            payload: 已序列化的请求数据。
            session_id: 会话 ID，透传给 RPC 层。

        Returns:
            Agent 返回的文本数据，若解析失败会抛出异常。
        """
        entry = self.registry.find(keyword)
        if entry is None:
            raise ValueError(f"未找到与关键字 {keyword} 匹配的 Agent")

        client = entry["client"]
        task = await client.start_task(session_id=session_id, user_input=payload)
        text = _extract_text_from_task(task)
        if text is None:
            raise ValueError(f"{entry['name']} agent 未返回文本结果")
        return text

    def fun_call_agent(self, state:ChatGraphState)->str:
        session_id = state["session_id"]
        user_text = state["user_input"]
        session_data = state["session_data"]
        now_task = session_data["now_task"]
        material = session_data["material"]
        if self.mode == 'test':
            return f'call {now_task}'
        if now_task == "outline":
            res = self.outline_writer.call(session_data)
            state["session_data"]["material"]["outline"] = res
        if now_task == 'screen':
            res = self.screen_writer.call(session_data)
            state["session_data"]["material"]["screen"] = res
        if now_task == "animator":
            video = self.animator.call(session_data)
            state["session_data"]["material"]["video_address"].append(video)
            res = '已完成第'+str(session_data["video_generating"])+'个视频生成'
            session_data["video_generating"] += 1
        return res
    
    def _get_session_state(self, session_id: str) -> Dict[str, Any]:
        """返回或创建指定会话的运行时状态字典。
        Args:
            session_id: 会话标识，用于索引内部缓存。

        Returns:
            包含确认标记、候选商品、任务拆解等字段的可变字典。
        """
        self._sessions = self.userfile.load_session()
        session_data = self._sessions.get(session_id)
        if session_data is None:
            session_data = {
                "material": {
                    "idea": None,
                    "outline": [],
                    "screen": [],
                    "video_address": [],
                },
                "chat_with_assistant":True,
                "modify_request": {
                    "outline": None,
                    "screen": None,
                },
                "modify_num": None,
                "video_generating": 0,
                "editing_screen": None,
                "message_count": 0,
                "now_task" : "imagination",
                "now_state":"None",
            }
            self._sessions[session_id] = session_data
        return session_data

    def assistant_node(self,state:ChatGraphState)->ChatGraphState:
        session_id = state["session_id"]
        user_text = state["user_input"]
        session_data = state["session_data"]
        now_task = session_data["now_task"]
        material = session_data["material"]
        now_state = session_data["now_state"]
    
        if now_state == "create":
            agentans = self.fun_call_agent(state)
            state['session_data']["now_state"] = "modify_comfirm"
            state['reply'] = AssistantReply(agentans)
            if state['session_data']['video_generating'] >= len(state['session_data']['material']['screen']):
                state['session_data']['chat_with_assistant'] = False
            #state['reply'].text += '\n是否需要修改？'
            return state
        
        if self.mode == 'test':
            ans = '这里是assistant'
        else:
            ans = self.assistant.call(user_text,session_data)
        idea = extract_idea(ans)
        if now_task == "imagination":
            if len(idea)!=0:
                state['session_data']['material']['idea'] = idea
            state['reply'] = AssistantReply(ans)
        
        if now_state == 'modify':
            state['session_data']['modify_request'][now_task] = ans
            state['reply'] = AssistantReply(ans)
        
        return state
        
    async def handle_user_input(self, session_id: str, user_input: str) -> ChatGraphState:
        ##为了适配单次调用，需要去除内部的所有阻塞程序
        """主入口：接收用户文本并交由 LangGraph 路由，返回回复。

        Args:
            session_id: 会话唯一标识，区分多用户上下文。
            user_input: 用户当前输入文本。

        Returns:
            `ChatGraphState`，包含会话状态、用户输入、回复等。
        """
        text = (user_input or "").strip()
        if not text:
            reply =  AssistantReply("请告诉我您的需求或问题，我会尽力帮助。")

        session_data = self._get_session_state(session_id)

        def _finalize(reply: AssistantReply) -> AssistantReply:
            """统一在返回前递增消息计数并回传回复。"""
            session_data["message_count"] = session_data.get("message_count", 0) + 1
            return reply

        if session_data.get("pending_candidates"):
            # 若存在待确认的候选商品，优先处理用户对当前商品的反馈。
            reply = await self._handle_pending_candidates(session_id, session_data, text)
            return _finalize(reply)

        graph_state: ChatGraphState = {
            "session_id": session_id,
            "user_input": text,
            "session_data": session_data,
            "reply": [],
        }

        # 通过 LangGraph 统一路由当前对话输入。
        graph_state["session_data"] = self.route_state(graph_state)
        graph_state["session_data"] = self.route_task(graph_state)
        result_state = await self._graph.ainvoke(graph_state)
        reply = result_state.get("reply")
        if not isinstance(reply, AssistantReply):
            fallback_text = result_state.get("response", "抱歉，我暂时无法处理该请求。")
            reply = AssistantReply(str(fallback_text))
        self.userfile.save_content(self.project_name,result_state['session_data']['material'],result_state['session_id'])
        self.userfile.save_session(result_state['session_id'],result_state['session_data'])
        check_state(result_state)
        if result_state['session_data']['chat_with_assistant'] == False:
            reply.end_session = True
            merge_videos(result_state['session_data']['material']['video_address'],self.userfile.project_path+self.project_name+'/'+self.project_name+'.mp4')
        # 维护对话轮次计数，便于后续做上下文压缩等扩展。
        result_state['reply'] = _finalize(reply)
        return result_state

    def route_state(self,state:ChatGraphState):
        session_id = state["session_id"]
        session_data = state["session_data"]
        intend = state["user_input"]
        now_task = session_data["now_task"]
        now_state = session_data["now_state"]
        if session_data["now_task"] != "imagination" and session_data["now_state"] == 'modify_comfirm':
            #intend = input('您是否觉得内容需要修改？(需要修改/不需要)：')##这里有前端后改为按钮
            if intend == '需要修改':
                session_data['now_state'] = 'modify'
                num = int(input('请选择需要修改的内容序号：'))##这里有前端后改为按钮
                session_data['modify_num'] = num
                if now_task == 'animator':
                    session_data['now_task'] = 'screen'
            if intend == '不需要':
                session_data['now_state'] = 'create'
                if now_task == 'outline':
                    session_data['now_task'] = 'screen'
                if now_task == 'screen':
                    session_data['now_task'] = 'animator'
        return session_data
    
    def route_task(self,state:ChatGraphState):
        session_id = state["session_id"]
        session_data = state["session_data"]
        user_text = state["user_input"]
        now_task = session_data["now_task"]
        now_state = session_data["now_state"]
        if CONFIRM_TEXT.intersection(set(user_text.split())):
            print('收到确认指令')##这里有前端后改为按钮“确认”
            if now_task == "imagination":
                session_data['now_task'] = 'outline'
            session_data['now_state'] = 'create'
        return session_data
    
    def _build_graph(self) -> StateGraph:
        builder = StateGraph(ChatGraphState)
        builder.add_node("assistant",self.assistant_node)
        builder.set_entry_point("assistant")
        builder.add_edge("assistant",END)
        return builder.compile()
    
def check_state(state:ChatGraphState):
    session_id = state["session_id"]
    session_data = state["session_data"]
    print('session_id:',session_id)
    for k in session_data.keys():
        print(k,session_data[k])

async def _ensure_partners_ready(clients: Dict[str, AipRpcClient]) -> None:
    """在 CLI 启动前检测各 Agent 服务是否可用。

    Args:
        clients: 名称到 RPC 客户端的映射。

    Raises:
        RuntimeError: 任一服务返回错误或无法连接时抛出。
    """
    errors: List[str] = []
    for name, client in clients.items():
        health_url = _rpc_to_health_url(client.partner_url)
        print(health_url)
        try:
            response = await client.http_client.get(health_url, timeout=10.0)
            if response.status_code >= 500:
                errors.append(f"{name}: HTTP {response.status_code}")
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"{name}: {exc}")

    if errors:
        detail = "\n".join(errors)
        raise RuntimeError(
            "部分 Agent 服务不可用，请检查后重试:\n" + detail
        )

def _rpc_to_health_url(url: str) -> str:
    """将 RPC 地址转换为健康检查 URL。

    Args:
        url: 形如 https://host/path 的 RPC 地址。

    Returns:
        指向根路径的 URL，供健康检查接口使用。
    """
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/", "", ""))

def run_test():
    user = 'czx'
    userfile = UserFile(user)
    project_name = input("请输入项目名称: ")
    mode = input("test or use:")
    orchestrator = PersonalAssistantOrchestrator(clients=None,userfile=userfile,project_name=project_name,mode=mode)
    session_id = orchestrator.main_session_id
    while 1:
        user_input = input("用户：").strip()
        res_state = asyncio.run(orchestrator.handle_user_input(session_id,user_input))
        reply = res_state['reply']
        if isinstance(reply.text, str):
            print(f"助手: {reply.text}\n")
        if isinstance(reply.text, list):
            for i in reply.text:
                print(i)
        if reply.end_session:
            break

def acps():
    user = 'czx'
    userfile = UserFile(user)
    mtls_config = load_mtls_config_from_json(
        CLIENT_CONFIG_JSON, cert_dir=os.path.join(_PROJECT_ROOT, "certs")
    )
    ssl_context = mtls_config.create_client_ssl_context()
    clients = asyncio.run(_initialize_clients_via_discovery(ssl_context))
    print(mtls_config)
    asyncio.run(_ensure_partners_ready(clients))
    orchestrator = PersonalAssistantOrchestrator(clients,userfile)
    print('init success')
    

if __name__ == "__main__":
    #acps()
    run_test()



