import os
from volcenginesdkarkruntime import Ark
import json
import os
from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import (Part, Task, TextPart, UnsupportedOperationError)
from a2a.utils import (completed_task, new_artifact)
from a2a.utils.errors import ServerError
import asyncio
#from langchain.checkpoint.memory import InMemorySaver
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate


import time
from tools.tool_hub import ark_web_search as web_search_tool
from tools.web_search import web_search
from base import CONTEXT_CACHE_TIME

assistant_prompt = PromptTemplate.from_template('''
【角色设定】
你是一位专业、耐心、充满活力的AI视频创作导演助手，擅长引导用户从模糊的创意到具体的视频制作需求，正在辅助用户使用视频生成模型进行创作。

【核心任务】
{task}

【搜索工具使用规则】
必要的时候，请使用function call调用联网搜索工具，上网搜索资料。用户每次输入你只能使用一次搜索工具。

【用户特点】
- 用户可能没有视频创作经验，不了解视频制作流程
- 用户可能不会主动提供所有必要信息，需要你引导提问

【视频创作核心要素（这4个尽量确认）】
- 视频主题/核心创意：用户想要表达什么内容或故事？
- 视频风格：写实/科幻/卡通/悬疑等？
- 视频时长：建议控制在1分钟以内（短视频平台友好，且易于操作）
- 关键角色：人物/动物/物体的特点和关系
（还需要添加其他你认为重要的元素）
（并且在递交需求给writer智能体之前，要确认用户是否还有其他需要添加的元素）

【回复格式要求】
1. 你的回复必须是纯JSON格式，不允许包含任何其他文本或格式！
    请严格按照以下要求输出JSON格式字符串，**必须遵守以下规则**：
    1. 仅输出JSON，无任何额外文字、注释、说明；
    2. JSON字符串中所有换行必须用转义符\\n表示，禁止出现真实换行；
    3. 所有字段名和字符串值必须用双引号包裹，禁止使用单引号；
    4. 禁止添加任何JSON注释（// 或 /* */）。
2. JSON必须包含以下字段：
   - idea：当前我们确认的视频创意想法，详细描述视频的主题、风格、时长、角色等核心要素
   - chat：与用户进行对话的内容
3. 示例：
   - 初始阶段：{{"idea": "当前我们还没有确认具体想法。", "chat": "你需要先描述一下你想要创作的视频类型（如科幻、动作等）和主要角色。"}}
   - 确认部分信息后：{{"idea": "当前我们的想法是做一个关于太空探索的科幻视频，其中包含宇航员和机器人角色", "chat": "你需要确认视频的时长（建议30秒）和是否需要加入背景音乐。"}}
   - 信息完整后：{{"idea": "当前我们已确认完整的视频创意：\n- 视频主题：太空探索科幻故事\n- 视频风格：科幻写实\n- 视频时长：30秒\n- 关键角色：宇航员和智能机器人", "chat": "你需要确认视频的时长（建议30秒）和是否需要加入背景音乐。"}}
   - 修改阶段（传入的material里outline、screen字段不为空）：{{"idea": "当前我们的修改需求是....", "chat": "我们现在要修改的分镜是.....你有什么需求？"}}

【注意】
以上的对话只是一个示例，用户真正的输入在'user'部分。

【后续工作流】
你后续有负责视频大纲的智能体、负责具体分镜提示词写作的智能体、负责视频生成的智能体。
''')

task_to_prompt = {
    "imagination":"和用户对话以帮用户寻找、激发灵感，或引导用户将用户的灵感变成具体的想法。",
    "outline":"和用户对话，确认他想要如何修改大纲，确保他的修改方向与他的想法相符。最后输出要交给outline_writer智能体的大纲修改建议。",
    "screen":"和用户对话，确认他想要如何修改分镜脚本，确保想法足够准确，并生成给分镜写作者的详细修改建议",
    "background":"和用户对话，确认他想要如何修改背景提示词，确保想法足够准确。背景提示词是用于驱动图片生成模型生成这个分镜的背景图片的提示词。",
    "figure":"和用户对话，确认他想要如何修改角色形象提示词，确保想法足够准确。角色形象提示词是用于驱动图片生成模型生成这个分镜的角色形象图片的提示词。",
    "story_board":"和用户对话，确认他想要如何修改分镜首帧提示词，确保想法足够准确。",
    "script":"和用户对话，确认他想要如何修改分镜运动脚本，确保想法足够准确。",
}

material_prompt = PromptTemplate.from_template('''
这是用户当前的创作材料：
{material}
其中，idea是用户通过和你聊天的过程确定的暂时的创作想法，outline是大纲写作者写的视频大纲，screen是分镜写作者写的创作分镜提示词。
''')


# 请确保您已将 API Key 存储在环境变量 ARK_API_KEY 中
# 初始化Ark客户端，从环境变量中读取您的API Key
client = Ark(
    # 此为默认路径，您可根据业务所在地域进行配置
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    # 从环境变量中获取您的 API Key。此为默认方式，您可根据需要进行修改
    api_key='c96dbd1f-aeab-461c-90d6-8096b0baeecd',
)

class Assistant:
    def __init__(self,user_name,project_name):
        self.user_name = user_name
        self.project_name = project_name
    
    def init_assistant(self,user_message,material,history,session_data):
        completion = client.responses.create(
        # 指定您创建的方舟推理接入点 ID，此处已帮您修改为您的推理接入点 ID
            model="doubao-seed-1-6-flash-250828",
            input=[
                {
                    'role':'system',
                    'content':assistant_prompt.invoke({'task':task_to_prompt["imagination"]}).to_string()
                },
                {
                    'role':'system',
                    'content':material_prompt.invoke({'material':json.dumps(material, ensure_ascii=False)}).to_string()
                },
                {
                    'role':'system',
                    'content':history
                },
                {
                    'role':'user',
                    'content':user_message
                }
            ],
            caching={"type": "enabled"}, 
            text={"format":{"type": "json_object"}},
            tools = web_search_tool,
            thinking={"type": "disabled"},
            expire_at=int(time.time()) + CONTEXT_CACHE_TIME
        )
        last_id = completion.id
        result, last_id = self.next_call(completion, session_data,last_id)
        return result, last_id
    
    def call(self, message: str,session_data:dict) -> tuple:
        now_task = session_data["now_task"]
        material = session_data["material"]
        modify_material = None
        history = self.load_and_format_chat_history()
        if session_data['modify_num'] != []:
            modify_material = session_data['material'][now_task][session_data['modify_num'][session_data['have_modify']]-1]
        input_prompt = [
                {
                    'role':'system',
                    'content':assistant_prompt.invoke({'task':task_to_prompt[now_task]}).to_string()
                },
                {
                    'role':'system',
                    'content':material_prompt.invoke({'material':json.dumps(material, ensure_ascii=False)}).to_string()
                },
                {
                    'role':'user',
                    'content':message
                }
            ]
        if modify_material != None:
            input_prompt.append({
                'role':'system',
                'content':'现在我们需要修改的内容：'+modify_material
            })
        try:
            # 检查last_id是否存在且不为None
            if not session_data['last_id']['assistant']:
                # 如果last_id不存在，调用init_assistant方法
                return self.init_assistant(message, material, history, session_data)
            
            completion = client.responses.create(
            # 指定您创建的方舟推理接入点 ID，此处已帮您修改为您的推理接入点 ID
                model="doubao-seed-1-6-flash-250828",
                previous_response_id = session_data['last_id']['assistant'],
                input=input_prompt,
                caching={"type": "enabled"}, 
                thinking={"type": "disabled"},
                text={"format":{"type": "json_object"}},
                expire_at=int(time.time()) + CONTEXT_CACHE_TIME
            )
            last_id = completion.id
            result, last_id = self.next_call(completion, session_data,last_id)
            return result, last_id
        except Exception as e:
            # 捕获API错误，特别是last_id失效时的400错误
            error_msg = str(e)
            # 检查HTTP状态码400或404，以及错误信息中的"not found"关键字
            if "400" in error_msg or "404" in error_msg or "not found" in error_msg.lower():
                # 如果是last_id失效错误，调用init_assistant方法重新初始化
                return self.init_assistant(message, material, history, session_data)
            else:
                # 其他错误，重新抛出
                raise e
    
    def next_call(self,previous_message:str, session_data:dict,last_id:str):
        cnt = 0
        while True:
            function_call = next(
                (item for item in previous_message.output if item.type == "function_call"),None
            )
            if function_call is None:
                return previous_message.output[-1].content[0].text,last_id
            else:
                call_id = function_call.call_id
                call_arguments = function_call.arguments
                arg = json.loads(call_arguments)
                query = arg["query"]
                result = web_search(query,cnt)
                cnt += 1
                completion = client.responses.create(
                    model="doubao-seed-1-6-flash-250828",
                    previous_response_id = last_id,
                    input=[
                        {
                            'type':'function_call_output',
                            'call_id':call_id,
                            'output':json.dumps(result, ensure_ascii=False)
                        }
                    ],
                    caching={"type": "enabled"}, 
                    text={"format":{"type": "json_object"}},
                    thinking={"type": "disabled"},
                    expire_at=int(time.time()) + CONTEXT_CACHE_TIME
                )
                last_id = completion.id
                previous_message = completion
        return (previous_message.output[-1].content[0].text,last_id)

    def load_and_format_chat_history(self):
        """从本地加载对话历史并格式化为字符串
        
        Returns:
            str: 格式化的对话历史字符串，如果没有对话历史则返回"当前没有对话历史"
        """
        from file_manage import UserFile
        import os
        
        # 创建UserFile实例
        user_file = UserFile(self.user_name)
        
        # 检查项目是否存在
        if self.project_name not in user_file.user_project:
            return "当前没有对话历史"
        
        # 加载对话历史
        chat_history = user_file.load_chat_history(self.project_name)
        
        # 如果没有对话历史，返回提示
        if not chat_history:
            return "当前没有对话历史"
        
        # 只保留最近的10条对话
        recent_chat_history = chat_history[-10:]
        
        # 格式化对话历史
        formatted_history = []
        # 计算起始序号，保持对话序号的连续性
        start_index = len(chat_history) - len(recent_chat_history) + 1
        for i, history_item in enumerate(recent_chat_history, start_index):
            user_content = history_item.get('user', '')
            assistant_content = history_item.get('assistant', '')
            formatted_history.append(f"对话 {i}：\n用户：{user_content}\n助手：{assistant_content}\n")
        
        return '\n'.join(formatted_history)

class AssistantExecuter(AgentExecutor):
    def __init__(self):
        self.agent = Assistant()
    
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        actual_message = context.message.parts[0].root.text  # 实际的 Message 对象
        
        
        # 在事件循环中运行Decision_Agent
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            self.agent.call,
            actual_message
        )
        
        # 从JSON格式转换回文本格式
        result_text = json.dumps(result, ensure_ascii=False)
        print(f"Decision Agent Result: {result_text},Type:{type(result_text)}")
        # 将结果封装到artifacts中返回
        await event_queue.enqueue_event(
            completed_task(
                context.task_id,
                context.context_id,
                [new_artifact(parts=[Part(root=TextPart(text=result_text))],name = 'test')],
                [context.message],
            )
        )
    
    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())
    
if __name__ == "__main__":
    test_model()