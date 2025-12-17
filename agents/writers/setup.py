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

from screenwriter import ScreenwriterExecuter

def main(host: str, port: int):
    capabilities = AgentCapabilities(streaming=False)
    decision_skill = AgentSkill(
        id='写作Agent',
        name='剧作家',
        description='理解用户输入目的并创作符合要求的剧本、分镜大纲',
        tags=['写作', '剧本创作', '分镜大纲'],
        examples=['我想创作一个有关美食的纪录片，请帮我创作一个分镜大纲'],
    )

    agent_card = AgentCard(
        name='剧作家 Agent',
        description='分析用户需求并创作符合要求的剧本、分镜大纲的智能助手',
        url=f'http://{host}:{port}',
        version='1.0.0',
        defaultInputModes=['text'],
        defaultOutputModes=['text'],
        capabilities=capabilities,
        skills=[decision_skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=ScreenwriterExecuter(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )
    import uvicorn

    uvicorn.run(server.build(), host=host, port=port)

url = 'http://127.0.0.1:10007/.well-known/agent-card.json'
if __name__ == '__main__':
    main("127.0.0.1", 10007)