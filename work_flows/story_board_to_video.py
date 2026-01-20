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
from base import ChatGraphState
from base import AssistantReply
from base import CONFIRM_TEXT
from base import extract_idea
from base import check_state
from base import AgentEntry
from base import AipRpcClient
from base import Set, Dict, List, Optional
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
            self.project_name = self.userfile.init_project(self.project_name,self.main_session_id)
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
            else:
                ans = self.outline_writer.call(session_data)
            state['session_data']['material']['outline'].append(ans)
            state['reply'] = AssistantReply(ans)
            state['session_data']['now_state'] = 'modify_confirm'
            return state
        if now_state == 'modify':
            if self.mode == 'test':
                ans = '这里是outline'
            else:
                ans = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['outline'] = ans
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
            else:
                ans = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['background'] = ans
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
            else:
                ans = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['background'] = ans
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
            else:
                ans = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['figure'] = ans
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
            else:
                ans = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['figure'] = ans
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
            else:
                ans = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['story_board'] = ans
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
            else:
                ans = self.assistant.call(user_text,session_data)
            state['reply'] = AssistantReply(ans)
            state['session_data']['modify_request']['script'] = ans
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