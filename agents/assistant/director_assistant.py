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
import prompt_hub
import time

# 请确保您已将 API Key 存储在环境变量 ARK_API_KEY 中
# 初始化Ark客户端，从环境变量中读取您的API Key
client = Ark(
    # 此为默认路径，您可根据业务所在地域进行配置
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    # 从环境变量中获取您的 API Key。此为默认方式，您可根据需要进行修改
    api_key='c96dbd1f-aeab-461c-90d6-8096b0baeecd',
)

def test_model():
    completion = client.chat.completions.create(
    # 指定您创建的方舟推理接入点 ID，此处已帮您修改为您的推理接入点 ID
        model="doubao-seed-1-6-251015",
        tools = [{"type":"web_search"}],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text", 
                        "text": "帮我找一下最近很火的纪录片题材有哪些"
                    },
                ],
            }
        ],
        reasoning_effort="medium",
        
    )
    print(completion.choices[0].message.content)

class Assistant:
    def __init__(self):
        self.last_id = None
    
    def init_assistant(self):
        completion = client.responses.create(
        # 指定您创建的方舟推理接入点 ID，此处已帮您修改为您的推理接入点 ID
            model="doubao-seed-1-6-251015",
            tools = [{"type":"web_search"}],
            input=[
                {
                    'role':'system',
                    'content':prompt_hub.assistant_prompt
                }
            ],
            caching={"type": "enabled"}, 
            thinking={"type": "disabled"},
            expire_at=int(time.time()) + 360
        )
        self.last_id = completion.id
        return completion.output[-1].content[0].text
    
    def call(self, message: str) -> str:
        if not self.last_id:
            return self.init_assistant()
        completion = client.responses.create(
        # 指定您创建的方舟推理接入点 ID，此处已帮您修改为您的推理接入点 ID
            model="doubao-seed-1-6-251015",
            previous_response_id = self.last_id,
            tools = [{"type":"web_search"}],
            input=[
                {
                    'role':'user',
                    'content':message
                }
            ],
            caching={"type": "enabled"}, 
            thinking={"type": "disabled"},
            expire_at=int(time.time()) + 360
        )
        self.last_id = completion.id
        return completion.output[-1].content[0].text

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