from fastapi import FastAPI, HTTPException
import uvicorn
import os
import asyncio
from pydantic import BaseModel
from typing import Dict, Any
import uuid

# 创建FastAPI应用
app = FastAPI(
    title="后端服务",
    description="用于前端对接的后端API服务",
    version="1.0.0"
)

# 请求模型
class WorkRequest(BaseModel):
    project_name: str
    user_input: str
    user_id: str

# 响应模型
class AssistantReply:
    def __init__(self, text, awaiting_followup=True, end_session=False):
        self.text = text
        self.awaiting_followup = awaiting_followup
        self.end_session = end_session

# 模拟UserFile类
class UserFile:
    def __init__(self, user_id):
        self.user = user_id
        self.user_project = []
        self.project_content = {}
        self.user_path = f'./user_files/{user_id}'
        self.project_path = f'{self.user_path}/projects/'
        # 创建必要的目录，如果它们不存在
        os.makedirs(self.user_path, exist_ok=True)
        os.makedirs(self.project_path, exist_ok=True)
    
    def init_project(self, project_name):
        return project_name
    
    def load_session(self):
        return {}
    
    def save_content(self, project_name, material, session_id):
        pass
    
    def save_session(self, session_id, session_data):
        pass

# 模拟PersonalAssistantOrchestrator类
class PersonalAssistantOrchestrator:
    def __init__(self, clients=None, userfile=None, project_name=None, mode='test'):
        self.userfile = userfile
        self.project_name = project_name
        self.mode = mode
        self.main_session_id = f"session-{uuid.uuid4()}"
        self._sessions = {}
    
    def _get_session_state(self, session_id):
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "material": {
                    "idea": None,
                    "outline": [],
                    "screen": [],
                    "video_address": [],
                },
                "chat_with_assistant": True,
                "modify_request": {
                    "outline": None,
                    "screen": None,
                },
                "modify_num": None,
                "video_generating": 0,
                "editing_screen": None,
                "message_count": 0,
                "now_task": "imagination",
                "now_state": "None",
            }
        return self._sessions[session_id]
    
    async def handle_user_input(self, session_id, user_input):
        session_data = self._get_session_state(session_id)
        reply = AssistantReply(f"已接收您的请求：{user_input}")
        return {
            "session_id": session_id,
            "user_input": user_input,
            "session_data": session_data,
            "reply": reply
        }

# 健康检查路由
@app.get("/")
def read_root():
    return {
        "message": "后端服务运行正常",
        "version": "1.0.0"
    }

## 示例API路由
@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "service": "backend-api"
    }

# work API端点
@app.post("/api/v1/work")
async def work(request: WorkRequest):
    try:
        project_name = request.project_name
        user = request.user_id
        user_input = request.user_input
        userfile = UserFile(user)
        
        # 创建PersonalAssistantOrchestrator实例
        orchestrator = PersonalAssistantOrchestrator(clients=None, userfile=userfile, project_name=project_name, mode='test')
        
        # 调用handle_user_input方法处理用户输入
        result_state = await orchestrator.handle_user_input(orchestrator.main_session_id, user_input)
        
        # 从结果状态中提取回复
        reply = result_state.get('reply')
        if not isinstance(reply, AssistantReply):
            fallback_text = result_state.get("response", "抱歉，我暂时无法处理该请求。")
            reply = AssistantReply(str(fallback_text))
        
        # 返回结果
        return {
            "success": True,
            "message": reply.text,
            "awaiting_followup": reply.awaiting_followup,
            "end_session": reply.end_session,
            "project_name": orchestrator.project_name,
            "session_id": orchestrator.main_session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # 启动uvicorn服务器
    uvicorn.run(
        "app_simple:app",
        host="0.0.0.0",
        port=8003,
        reload=True
    )