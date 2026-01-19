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


assistant_prompt = PromptTemplate.from_template('''
你是一个充满活力的导演助手，正在辅助用户使用视频生成模型进行创作。你的任务是{task}。必要的时候，请使用联网搜索工具上网搜索资料。
！注意！你不能连续发起联网搜索工具调用请求，每次只能发起一次。
用户没有使用视频生成模型的经验，因此不知道如何在提示词中表达他的想法。此外，用户还很有可能没有进行过视频创作，不知道创作一个视频需要确认哪些要素
每次给用户返回信息时，必须在信息的最开头加上当前你与用户确认过的想法，例如：“当前我们的想法是做一个...视频，其中....”这部分内容要求你根据你和用户的对话记录，尽可能多地把用户的想法包含在其中，例如角色形象、场景氛围、视频时长、视频主题等。
当你认为需求的要素齐全后，可以在最后确认需求后，将需求递交给writer智能体。
！注意！以上的对话只是一个示例，用户真正的输入在'user'部分，用户若没有提到他的需求，想法确认部分就写“当前我们还没有确认过的想法。”
！注意！我们的任务是进行视频创作，请不要在回复中包含任何与视频创作无关的内容。
你回复的内容只是视频制作的思路，不需要太过详细，详细的内容会由后续的智能体生成
你后续有负责视频大纲的智能体、负责具体分镜提示词写作的智能体、负责视频生成的智能体。
''')

task_to_prompt = {
    "imagination":"和用户对话以帮用户寻找灵感，或引导用户将用户的灵感变成具体的想法。",
    "outline":"和用户对话，确认他想要如何修改大纲，确保他的修改方向与他的想法相符。",
    "screen":"和用户对话，确认他想要如何修改分镜脚本，确保想法足够准确",
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
    def __init__(self):
        self.last_id = None
    
    def init_assistant(self,user_message,material):
        completion = client.responses.create(
        # 指定您创建的方舟推理接入点 ID，此处已帮您修改为您的推理接入点 ID
            model="doubao-seed-1-6-251015",
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
                    'role':'user',
                    'content':user_message
                }
            ],
            tools = web_search_tool,
            caching={"type": "enabled"}, 
            thinking={"type": "disabled"},
            expire_at=int(time.time()) + 360
        )
        self.last_id = completion.id
        return self.next_call(completion)
    
    def call(self, message: str,session_data:dict) -> str:
        now_task = session_data["now_task"]
        material = session_data["material"]
        modify_material = None
        if session_data['modify_num'] != None:
            modify_material = session_data['material'][now_task][session_data['modify_num']-1]
        if not self.last_id:
            return self.init_assistant(message,material)
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
        completion = client.responses.create(
        # 指定您创建的方舟推理接入点 ID，此处已帮您修改为您的推理接入点 ID
            model="doubao-seed-1-6-251015",
            previous_response_id = self.last_id,
            input=input_prompt,
            caching={"type": "enabled"}, 
            thinking={"type": "disabled"},
            expire_at=int(time.time()) + 360
        )
        self.last_id = completion.id
        return self.next_call(completion)
    
    def next_call(self,previous_message:str):
        while True:
            function_call = next(
                (item for item in previous_message.output if item.type == "function_call"),None
            )
            if function_call is None:
                return previous_message.output[-1].content[0].text
            else:
                call_id = function_call.call_id
                call_arguments = function_call.arguments
                arg = json.loads(call_arguments)
                query = arg["query"]
                result = web_search(query)
                print('search query:',query)
                completion = client.responses.create(
                    model="doubao-seed-1-6-251015",
                    previous_response_id = self.last_id,
                    input=[
                        {
                            'type':'function_call_output',
                            'call_id':call_id,
                            'output':json.dumps(result, ensure_ascii=False)
                        }
                    ],
                    caching={"type": "enabled"}, 
                    thinking={"type": "disabled"},
                    expire_at=int(time.time()) + 360
                )
                self.last_id = completion.id
                previous_message = completion
        return previous_message.output[-1].content[0].text

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