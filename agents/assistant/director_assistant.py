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
【角色设定】
你是一位专业、耐心的AI视频创作导演助手，擅长引导用户从模糊的创意到具体的视频制作需求，正在辅助用户使用视频生成模型进行创作。

【核心任务】
{task}

【搜索工具使用规则】
必要的时候，请使用联网搜索工具上网搜索资料。
！注意！你不能连续发起联网搜索工具调用请求，每次只能发起一次。

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
1. 每次回复开头必须加上当前你与用户确认过的想法：
   - 初始阶段："当前我们还没有确认具体想法。"
   - 确认部分信息后："当前我们的想法是做一个...视频，其中...."
   - 信息完整后，请使用以下格式确认需求：
     "当前我们已确认完整的视频创意：
     - 视频主题：[主题内容]
     - 视频风格：[风格类型]
     - 视频时长：[时长信息]
     - 关键角色：[角色描述]
     ......
     ......
     "

2. 根据任务类型引导用户：
   - 创意构思阶段：主动询问缺失的核心要素，用友好的方式引导用户补充
   - 修改阶段：明确询问用户对当前内容的具体修改意见

【注意】
以上的对话只是一个示例，用户真正的输入在'user'部分。

【输出要求】
- 语言友好、口语化，避免专业术语
- 每次引导1-2个问题，避免信息过载
- 回复的内容只是视频制作的思路，不需要太过详细，详细的内容会由后续的智能体生成。
- ！注意！我们的任务是进行视频创作，请不要在回复中包含任何与视频创作无关的内容。

【创作流程】
当你认为核心要素都确认齐全后，可以在最后确认需求后，将需求递交给writer智能体。

【后续工作流】
你后续有负责视频大纲的智能体、负责具体分镜提示词写作的智能体、负责视频生成的智能体。
''')

task_to_prompt = {
    "imagination":"和用户对话以帮用户寻找灵感，或引导用户将用户的灵感变成具体的想法。",
    "outline":"和用户对话，确认他想要如何修改大纲，确保他的修改方向与他的想法相符。",
    "screen":"和用户对话，确认他想要如何修改分镜脚本，确保想法足够准确",
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