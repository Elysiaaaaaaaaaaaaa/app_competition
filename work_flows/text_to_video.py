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

import base
from transform_ import to_json, from_json
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
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
from base import get_agent_logger
from base import ChatGraphState
from base import AssistantReply
from base import CONFIRM_TEXT
from base import extract_idea
from base import check_state
logger = get_agent_logger(__name__)

class Text2VideoWorkflow:
    '''
    文本到视频工作流
    '''
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
        self.userfile.save_chat_history(self.project_name,result_state['session_data'])
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