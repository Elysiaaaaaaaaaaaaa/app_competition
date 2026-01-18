from fastapi import FastAPI, HTTPException
import uvicorn
import os
import asyncio
from pydantic import BaseModel
from typing import Dict, Any
from run_acps import PersonalAssistantOrchestrator, AssistantReply
from file_manage import UserFile

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
    mode: str

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
            "end_session": reply.end_session,
            "project_name": orchestrator.project_name,
            "session_id": orchestrator.main_session_id,
            "session_data": result_state['session_data']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # 启动uvicorn服务器
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8003,
        reload=True  # 开发模式下启用热重载
    )
