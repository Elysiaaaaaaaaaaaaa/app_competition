import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from a2a.server.apps.jsonrpc.starlette_app import A2AStarletteApplication
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)


import os

# 添加当前目录到系统路径

from director_assistant import AssistantExecuter

def main(host: str, port: int):
    capabilities = AgentCapabilities(streaming=False)
    decision_skill = AgentSkill(
        id='助手Agent',
        name='Muse',
        description='与用户交互，引导用户找到灵感并生成具体的想法',
        tags=['助手', '激发灵感', '想法形成'],
        examples=['我想创作一个纪录片，给我点灵感'],
    )

    agent_card = AgentCard(
        name='助手 Agent',
        description='分析用户需求并与用户交互，引导用户找到灵感并生成具体的想法',
        url=f'http://{host}:{port}',
        version='1.0.0',
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=capabilities,
        skills=[decision_skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=AssistantExecuter(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )
    import uvicorn

    uvicorn.run(server.build(), host=host, port=port)


if __name__ == '__main__':
    main("127.0.0.1", 10008)