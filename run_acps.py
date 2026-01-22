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
from langgraph.types import Command
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
from agents.painter.painter_qwen import Painter

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
    reply: AssistantReply

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
    :param ai_single_reply: AI的单次回复字符串（JSON格式）
    :return: 提取到的内容列表（无匹配则返回空列表）
    """
    try:
        # 尝试将AI回复解析为JSON
        reply_json = json.loads(ai_single_reply)
        # 提取idea字段
        if 'idea' in reply_json:
            idea_content = reply_json['idea']
            if idea_content.strip():
                return [idea_content.strip()]
    except json.JSONDecodeError:
        # 如果解析失败，返回空列表
        return []
    except Exception as e:
        # 其他异常也返回空列表
        return []
    return []

def safe_parse_llm_json(raw_str):
    """
    安全解析大模型输出的JSON字符串，兼容常见格式错误
    新增修复：markdown符号、特殊空格、控制字符、断字空格
    """
    if not raw_str:
        return {}
    
    # 步骤1：提取JSON主体（过滤大模型额外输出的文字）
    json_match = re.search(r"\{[\s\S]*\}", raw_str)
    if not json_match:
        return {}
    json_str = json_match.group()
    
    # 步骤2：修复常见错误（新增核心修复逻辑）
    fixed_str = (
        json_str
        # 修复1：删除markdown加粗符（最核心的报错原因）
        .replace("**", "")
        # 修复2：替换真实换行为转义符（保留原逻辑）
        .replace("\n", "\\n")
        # 修复3：单引号转双引号（保留原逻辑）
        .replace("'", '"')
        # 修复4：替换所有特殊空格（全角/不间断/制表符）为普通半角空格
        .replace("\u3000", " ").replace("\u00A0", " ").replace("\t", " ")
        # 修复5：合并连续空格（解决"短 视频""动 作"这类断字问题）
        .replace("  ", " ")
        # 修复6：清理不可见控制字符（\r/\b等）
        .replace("\r", "")
        # 修复7：去除首尾多余空格（保留原逻辑）
        .strip()
    )
    
    # 步骤3：容错解析（新增调试信息+终极兜底）
    try:
        return json.loads(fixed_str)
    except json.JSONDecodeError as e:
        print(f"JSON解析失败（已尽力修复）：{e}")
        # 终极兜底：即使解析失败，也用正则提取idea/chat字段
        idea_match = re.search(r'"idea":\s*"([\s\S]*?)"(?=,"chat")', fixed_str)
        chat_match = re.search(r'"chat":\s*"([\s\S]*?)"(?=}$)', fixed_str)
        return {
            "idea": idea_match.group(1).strip() if idea_match else "",
            "chat": chat_match.group(1).strip() if chat_match else ""
        }

class Text2VideoWorkflow:
    '''
    文本到视频工作流
    '''
    def __init__(self, clients: Dict[str, AipRpcClient],userfile:UserFile,project_name:str,mode:str):
        #self.clients = clients
        self.userfile = userfile
        self.project_name = project_name
        if self.project_name not in self.userfile.user_project:
            self.main_session_id = f"session-{uuid.uuid4()}"
            self.project_name = self.userfile.init_project(self.project_name, self.main_session_id, workflow_type='text2video')
        else:
            self.main_session_id = self.userfile.project_content[self.project_name]['session_id']
        
        self.mode = mode
        logger.info("event=cli_start session_id=%s user=%s", self.main_session_id,self.userfile.user)
        # 关键字注册表：支持用自然语言别名查找底层客户端。
        #self.registry = AgentRegistry(clients, AGENT_KEYWORD_ALIASES)
        self._history_store: Dict[str, List[AIMessage | HumanMessage | SystemMessage]] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}##会话记录加载到这里
        self._sessions = self.userfile.load_session()
        self.assistant = Assistant(user_name=self.userfile.user,project_name=self.project_name)
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
            res, last_id = self.outline_writer.call(session_data)
            state["session_data"]["material"]["outline"] = res
            state["session_data"]["last_id"]["outline_writer"] = last_id
        if now_task == 'screen':
            res, last_id = self.screen_writer.call(session_data)
            state["session_data"]["material"]["screen"] = res
            state["session_data"]["last_id"]["screen_writer"] = last_id
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
                "modify_num": [],
                "have_modify":0,
                "video_generating": 0,
                "editing_screen": None,
                "message_count": 0,
                "now_task" : "imagination",
                "now_state":"None",
                "last_id": {
                    "assistant": None,
                    "outline_writer": None,
                    "screen_writer": None
                },
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
            if state['session_data']['video_generating'] >= len(state['session_data']['material']['screen']) and now_task == "animator":
                state['session_data']['chat_with_assistant'] = False
            #state['reply'].text += '\n是否需要修改？'
            return state
        
        if self.mode == 'test':
            ans = '这里是assistant'
            idea = ans
            last_id = None
        else:
            ans, last_id = self.assistant.call(user_text,session_data)
            print(ans)
            ans_json = safe_parse_llm_json(ans)
            ans = ans_json['idea']+'\n'+ans_json['chat']
            idea = ans_json['idea']
        state['session_data']['last_id']['assistant'] = last_id
        if now_task == "imagination":
            state['session_data']['material']['idea'] = idea
            state['reply'] = AssistantReply(ans)
        
        if now_state == 'modify':
            state['session_data']['modify_request'][now_task] = ans
            state['reply'] = AssistantReply(ans)
        
        return state
        
    async def handle_user_input(self, session_id: str, user_input: str,modify_num:List[int]=[]) -> ChatGraphState:
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
        graph_state["session_data"]["modify_num"] = modify_num
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
        self.userfile.save_chat_history(self.project_name,result_state)
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
            if intend == '需要修改':
                session_data['now_state'] = 'modify'
                if now_task == 'animator':
                    session_data['now_task'] = 'screen'
            if intend == '不需要':
                session_data['now_state'] = 'create'
                if now_task == 'outline':
                    if session_data['have_modify'] < len(session_data['modify_num']):
                        session_data['have_modify'] += 1
                    else:
                        session_data['have_modify'] = 0
                        session_data['modify_num'] = []
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
    

class Image2VideoWorkflow:
    '''
    图片到视频工作流
    assistant->outline->image->script->animator
    '''
    def __init__(self, clients: Dict[str, AipRpcClient],userfile:UserFile,project_name:str,mode:str):
        #self.clients = clients
        self.userfile = userfile
        self.project_name = project_name
        if self.project_name not in self.userfile.user_project:
            self.main_session_id = f"session-{uuid.uuid4()}"
            self.project_name = self.userfile.init_project(self.project_name,self.main_session_id, workflow_type='image2video')
        else:
            self.main_session_id = self.userfile.project_content[self.project_name]['session_id']
        
        self.mode = mode
        logger.info("event=cli_start session_id=%s user=%s", self.main_session_id,self.userfile.user)
        # 关键字注册表：支持用自然语言别名查找底层客户端。
        #self.registry = AgentRegistry(clients, AGENT_KEYWORD_ALIASES)
        self._history_store: Dict[str, List[AIMessage | HumanMessage | SystemMessage]] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._sessions = self.userfile.load_session()
        self.assistant = Assistant()
        self.outline_writer = OutlineWriter()
        self.screen_writer = ScreenWriter()
        self.painter = Painter(name=self.project_name,download_link=self.userfile.project_path)
    
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
                    "background":{
                        "prompt":[],
                        "image_address":[],
                        "description":[]
                    },
                    "figure":{
                        "prompt":[],
                        "LoRA_module":[],
                        "description":[]
                    },
                    "screen": [{
                        'background_id':None,
                        'prompt':None,
                        'image_address':None,
                    }],
                    "story_board":[],
                    "video_address": [],
                },
                "chat_with_assistant":True,
                "modify_request": {
                    "outline": None,
                    "background":None,
                    "figure":None,
                    "story_board":None,
                    "script":None,
                },
                "modify_num": None,
                "background_generating": 0,
                "story_board_generating": 0,
                "video_generating": 0,
                "message_count": 0,
                "now_task" : "imagination",
                "now_state":"None",
                "last_id": {
                    "assistant": None,
                    "outline_writer": None,
                    "screen_writer": None
                },
            }
            self._sessions[session_id] = session_data
        return session_data
        
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

        graph_state: ChatGraphState = {
            "session_id": session_id,
            "user_input": text,
            "session_data": session_data,
            "reply": None,
        }

        # 通过 LangGraph 统一路由当前对话输入。
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
        self.userfile.save_chat_history(self.project_name,result_state)
        return result_state

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(ChatGraphState)
        builder.add_node("route_task",self.route_task)
        builder.add_node("confirm_task",self.confirm_task)
        builder.add_node("confirm_state",self.confirm_state)
        builder.add_node("imagination",self.imagination_node)
        builder.add_node("outline",self.outline_node)
        builder.add_node("figure_design",self.figure_design_node)
        builder.add_node("background_prompting",self.background_prompting_node)
        builder.add_node("background_painting",self.background_painting_node)
        builder.add_node("figure_prompting",self.figure_prompting_node)
        builder.add_node("story_board",self.story_board_node)
        builder.add_node("script",self.script_node)
        builder.add_node("animator",self.animator_node)
        builder.set_entry_point("route_task")
        builder.add_edge("imagination",END)
        return builder.compile()
    
    def route_task(self,state:ChatGraphState):
        session_id = state["session_id"]
        session_data = state["session_data"]
        user_text = state["user_input"]
        now_task = session_data["now_task"]
        now_state = session_data["now_state"]
        if user_text == '确认':
            print('收到确认指令')##这里有前端后改为按钮“确认”
            return Command(goto = 'confirm_task')
        if now_state == 'modify_confirm':
            return Command(goto = 'confirm_state')
        return Command(goto = now_task)

    def confirm_task(self,state:ChatGraphState):
        session_id = state["session_id"]
        session_data = state["session_data"]
        user_text = state["user_input"]
        now_task = session_data["now_task"]
        now_state = session_data["now_state"]

        if now_state == 'modify':
            state['session_data']['now_state'] = 'create'
            return Command(goto = now_task)
        if now_task == 'imagination':
            state['session_data']['now_task'] = 'outline'
            state['session_data']['now_state'] = 'create'
            return Command(update = {'session_data':state['session_data']},goto = 'outline')
    
    def confirm_state(self,state:ChatGraphState):
        session_id = state["session_id"]
        session_data = state["session_data"]
        user_text = state["user_input"]
        now_task = session_data["now_task"]
        now_state = session_data["now_state"]
        print('是否需要修改：',user_text)
        if user_text == '需要修改':
            state['session_data']['now_state'] = 'modify'
            return Command(update = {'session_data':state['session_data']},goto = now_task)
        if user_text == '不需要':
            state['session_data']['now_state'] = 'create'
            ##路由至下一个任务
            if now_task == 'outline':
                state['session_data']['now_task'] = 'figure_design'
            if now_task == 'figure_design':
                state['session_data']['now_task'] = 'background_prompting'
            if now_task == 'background_prompting':
                state['session_data']['now_task'] = 'background_painting'
            if now_task == 'background_painting':
                if session_data['background_generating']>=len(session_data['material']['outline']):
                    state['session_data']['now_task'] = 'figure_prompting'
                else:
                    state['session_data']['now_task'] = 'background_prompting'
                    state['session_data']['background_generating'] += 1
            if now_task == 'figure_prompting':
                state['session_data']['now_task'] = 'story_board'
            if now_task == 'story_board':
                if session_data['story_board_generating']>=len(session_data['material']['outline']):
                    state['session_data']['now_task'] = 'script'
                else:
                    state['session_data']['now_task'] = 'story_board'
                    state['session_data']['story_board_generating'] += 1
            if now_task == 'script':
                state['session_data']['now_task'] = 'animator'
            return Command(update = {'session_data':state['session_data']},goto = state['session_data']['now_task'])
        
        
    def imagination_node(self,state:ChatGraphState)->ChatGraphState:
        '''
            创作第一阶段，与助手对话，构建细化视频制作idea
        '''
        session_id = state["session_id"]
        user_text = state["user_input"]
        session_data = state["session_data"]
        now_task = session_data["now_task"]
        material = session_data["material"]
        now_state = session_data["now_state"]
        if self.mode == 'test':
            ans = '这里是assistant'
        else:
            ans = self.assistant.call(user_text,session_data)
        idea = extract_idea(ans)
        state['reply'] = AssistantReply(ans)
        if len(idea)!=0:
            state['session_data']['material']['idea'] = str(idea)
        return state

    def outline_node(self,state:ChatGraphState)->ChatGraphState:
        '''
            创作第二阶段，与助手对话，构建视频 outline
        '''
        session_id = state["session_id"]
        user_text = state["user_input"]
        session_data = state["session_data"]
        now_task = session_data["now_task"]
        material = session_data["material"]
        now_state = session_data["now_state"]
        if now_state == 'create':
            if self.mode == 'test':
                ans = '这里是outline'
                last_id = None
            else:
                ans, last_id = self.outline_writer.call(session_data)
            state['session_data']['material']['outline'].append(ans)
            state['reply'] = AssistantReply(ans)
            state['session_data']['last_id']['outline_writer'] = last_id
            state['session_data']['now_state'] = 'modify_confirm'
            return state
        if now_state == 'modify':
            if self.mode == 'test':
                ans = '这里是outline'
                last_id = None
            else:
                ans, last_id = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['outline'] = ans
            state['session_data']['last_id']['assistant'] = last_id
            return state
    
    def background_prompting_node(self,state:ChatGraphState)->ChatGraphState:
        session_id = state["session_id"]
        user_text = state["user_input"]
        session_data = state["session_data"]
        now_task = session_data["now_task"]
        material = session_data["material"]
        now_state = session_data["now_state"]
        if now_state == 'create':
            if self.mode == 'test':
                ans = '这里是background_prompting'
            else:
                ans = self.story_teller.call(session_data)
            state['session_data']['material']['background']['prompt'].append(ans)
            state['reply'] = AssistantReply(ans)
            state['session_data']['now_state'] = 'modify_confirm'
            return state
        if now_state == 'modify':
            if self.mode == 'test':
                ans = '这里是background_prompting'
                last_id = None
            else:
                ans, last_id = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['background'] = ans
            state['session_data']['last_id']['assistant'] = last_id
            return state
        
    def background_painting_node(self,state:ChatGraphState)->ChatGraphState:
        session_id = state["session_id"]
        user_text = state["user_input"]
        session_data = state["session_data"]
        now_task = session_data["now_task"]
        material = session_data["material"]
        now_state = session_data["now_state"]
        if now_state == 'create':
            if self.mode == 'test':
                ans = '这里是background_painting'
            else:
                ans = self.painter.call(session_data)
            state['session_data']['material']['background']['image_address'].append(ans)
            state['reply'] = AssistantReply(ans)
            state['session_data']['now_state'] = 'modify_confirm'
            return state
        if now_state == 'modify':
            if self.mode == 'test':
                ans = '这里是background_painting'
                last_id = None
            else:
                ans, last_id = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['background'] = ans
            state['session_data']['last_id']['assistant'] = last_id
            return state
    
    def figure_design_node(self,state:ChatGraphState)->ChatGraphState:
        session_id = state["session_id"]
        user_text = state["user_input"]
        session_data = state["session_data"]
        now_task = session_data["now_task"]
        material = session_data["material"]
        now_state = session_data["now_state"]
        if now_state == 'create':
            if self.mode == 'test':
                ans = '这里是figure_design'
            else:
                ans = self.story_teller.call(session_data)
            state['session_data']['material']['figure']['prompt'].append(ans)
            state['reply'] = AssistantReply(ans)
            state['session_data']['now_state'] = 'modify_confirm'
            return state
        if now_state == 'modify':
            if self.mode == 'test':
                ans = '这里是figure_design'
                last_id = None
            else:
                ans, last_id = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['figure'] = ans
            state['session_data']['last_id']['assistant'] = last_id
            return state

    def figure_prompting_node(self,state:ChatGraphState)->ChatGraphState:
        session_id = state["session_id"]
        user_text = state["user_input"]
        session_data = state["session_data"]
        now_task = session_data["now_task"]
        material = session_data["material"]
        now_state = session_data["now_state"]
        if now_state == 'create':
            if self.mode == 'test':
                ans = '这里是figure_prompting'
            else:
                ans = self.story_teller.call(session_data)
            state['session_data']['material']['figure']['prompt'].append(ans)
            state['reply'] = AssistantReply(ans)
            state['session_data']['now_state'] = 'modify_confirm'
            return state
        if now_state == 'modify':
            if self.mode == 'test':
                ans = '这里是figure_prompting'
                last_id = None
            else:
                ans, last_id = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['figure'] = ans
            state['session_data']['last_id']['assistant'] = last_id
            return state

    def story_board_node(self,state:ChatGraphState)->ChatGraphState:
        session_id = state["session_id"]
        user_text = state["user_input"]
        session_data = state["session_data"]
        now_task = session_data["now_task"]
        material = session_data["material"]
        now_state = session_data["now_state"]
        if now_state == 'create':
            if self.mode == 'test':
                board_address = '这里是story_board'
            else:
                board_address = self.painter.call(session_data)
            state['session_data']['material']['story_board'].append(board_address)
            state['reply'] = AssistantReply(board_address)
            state['session_data']['now_state'] = 'modify_confirm'
            return state
        if now_state == 'modify':
            if self.mode == 'test':
                ans = '这里是story_board'
                last_id = None
            else:
                ans, last_id = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['story_board'] = ans
            state['session_data']['last_id']['assistant'] = last_id
            return state
    
    def script_node(self,state:ChatGraphState)->ChatGraphState:
        '''
            创作第三阶段，与助手对话，构建视频 script
        '''
        session_id = state["session_id"]
        user_text = state["user_input"]
        session_data = state["session_data"]
        now_task = session_data["now_task"]
        material = session_data["material"]
        now_state = session_data["now_state"]   
        if now_state == 'create':
            if self.mode == 'test':
                ans = '这里是script'
            else:
                ans = self.script_writer.call(session_data)
            state['session_data']['material']['script'] = ans
            state['reply'] = AssistantReply(ans)
            state['session_data']['now_state'] = 'modify_confirm'
            return state
        if now_state == 'modify':
            if self.mode == 'test':
                ans = '这里是script'
                last_id = None
            else:
                ans, last_id = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['script'] = ans
            state['session_data']['last_id']['assistant'] = last_id
            return state
    
    def animator_node(self,state:ChatGraphState)->ChatGraphState:
        '''
            创作第五阶段，与助手对话，生成视频
        '''
        session_id = state["session_id"]
        user_text = state["user_input"]
        session_data = state["session_data"]
        now_task = session_data["now_task"]
        material = session_data["material"]
        now_state = session_data["now_state"]   
        if now_state == 'create':
            if self.mode == 'test':
                ans = '这里是animator'
            else:
                ans = self.animator.call(session_data)
            state['session_data']['material']['video_address'].append(ans)
            state['reply'] = AssistantReply(ans)
            state['session_data']['now_state'] = 'modify_confirm'
            return state
        
    
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
    orchestrator = Text2VideoWorkflow(clients=None,userfile=userfile,project_name=project_name,mode=mode)
    session_id = orchestrator.main_session_id
    while 1:
        user_input = input("用户：").strip()
        modify_num = userfile.load_session().get(session_id, {}).get("modify_num", [])
        if user_input == '需要修改':
            # 允许用户输入多个用逗号分隔的编号
            input_str = input("请输入需要修改的项目编号（多个编号用英文逗号分隔）: ")
            modify_num = [int(num.strip()) for num in input_str.split(',') if num.strip().isdigit()]
            print(modify_num)
        res_state = asyncio.run(orchestrator.handle_user_input(session_id,user_input, modify_num))
        reply = res_state['reply']
        if isinstance(reply.text, str):
            print(f"助手: {reply.text}\n")
        if isinstance(reply.text, list):
            for i in reply.text:
                print(i)
        if res_state['session_data']['now_state'] == 'modify_confirm':
            print('是否需要修改：')
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



