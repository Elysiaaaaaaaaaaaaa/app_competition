from fastapi import FastAPI, HTTPException, Request
import uvicorn
import os
import asyncio
from pydantic import BaseModel, ValidationError
from typing import Dict, Any
from run_acps import Text2VideoWorkflow, AssistantReply
from file_manage import UserFile

# 创建FastAPI应用
app = FastAPI(
    title="后端服务",
    description="用于前端对接的后端API服务",
    version="1.0.0"
)

# 定义统一的错误响应格式函数
def get_error_response(detail: str, status_code: int, example: dict = None) -> Dict[str, Any]:
    response = {
        "success": False,
        "error": {
            "code": status_code,
            "message": detail
        }
    }
    if example:
        response["example"] = example
    return response

# 请求模型
class WorkRequest(BaseModel):
    project_name: str
    user_input: str
    user_id: str
    mode: str

class UserIdRequest(BaseModel):
    user_id: str

class ProjectHistoryRequest(BaseModel):
    user_id: str
    project_name: str

class NewProjectRequest(BaseModel):
    user_id: str
    project_name: str
    workflow_type: str

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

# 全局异常处理
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    # 分析错误信息
    error_details = []
    for error in exc.errors():
        error_details.append({
            "field": ".".join(error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    # 确定当前请求的路径，返回相应的示例
    path = request.url.path
    example = None
    
    if path.endswith("/api/v1/work"):
        example = {
            "project_name": "测试项目",
            "user_input": "测试请求",
            "user_id": "测试用户ID",
            "mode": "test"
        }
    elif path.endswith("/api/v1/projects/list"):
        example = {
            "user_id": "测试用户ID"
        }
    elif path.endswith("/api/v1/projects/history"):
        example = {
            "user_id": "测试用户ID",
            "project_name": "测试项目"
        }
    elif path.endswith("/api/v1/projects/new"):
        example = {
            "user_id": "测试用户ID",
            "project_name": "新测试项目",
            "workflow_type": "text2video"
        }
    
    # 返回统一的错误响应
    return get_error_response(
        detail=f"请求参数验证失败: {', '.join([error['message'] for error in error_details])}",
        status_code=422,
        example=example
    )

# workflow API端点
@app.post("/api/v1/work")
async def work(request: WorkRequest):
    try:
        project_name = request.project_name
        user = request.user_id
        user_input = request.user_input
        userfile = UserFile(user)
        
        # 创建Text2VideoWorkflow实例
        orchestrator = Text2VideoWorkflow(clients=None, userfile=userfile, project_name=project_name, mode='test')
        
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
        return get_error_response(detail=str(e), status_code=500)

# 获取用户项目列表
@app.post("/api/v1/projects/list")
async def get_projects(request: UserIdRequest):
    try:
        user_id = request.user_id
        userfile = UserFile(user_id)
        
        # 获取所有会话数据
        sessions = userfile.load_session()
        
        # 构建项目列表
        projects = []
        for project_name in userfile.user_project:
            project_content = userfile.project_content[project_name]
            session_id = project_content.get('session_id')
            workflow_type = project_content.get('workflow_type', 'text2video')
            
            # 获取当前任务
            now_task = "imagination"
            if session_id and session_id in sessions:
                now_task = sessions[session_id].get('now_task', 'imagination')
            
            projects.append({
                "project_name": project_name,
                "workflow_type": workflow_type,
                "now_task": now_task
            })
        
        return {
            "success": True,
            "projects": projects
        }
    except Exception as e:
        return get_error_response(detail=str(e), status_code=500)

# 获取指定项目的对话历史
@app.post("/api/v1/projects/history")
async def get_project_history(request: ProjectHistoryRequest):
    try:
        user_id = request.user_id
        project_name = request.project_name
        userfile = UserFile(user_id)
        
        # 检查项目是否存在
        if project_name not in userfile.user_project:
            return get_error_response(detail=f"项目 {project_name} 不存在", status_code=404)
        
        # 获取对话历史
        chat_history = userfile.load_chat_history(project_name)
        
        return {
            "success": True,
            "chat_history": chat_history
        }
    except Exception as e:
        return get_error_response(detail=str(e), status_code=500)

# 新建项目
@app.post("/api/v1/projects/new")
async def create_project(request: NewProjectRequest):
    try:
        user_id = request.user_id
        project_name = request.project_name
        workflow_type = request.workflow_type
        
        # 验证工作流类型
        allowed_workflow_types = ['text2video', 'image2video']
        if workflow_type not in allowed_workflow_types:
            return get_error_response(
                detail=f"无效的工作流类型: {workflow_type}，只允许: {', '.join(allowed_workflow_types)}",
                status_code=400,
                example={
                    "user_id": user_id,
                    "project_name": project_name,
                    "workflow_type": "text2video"
                }
            )
        
        userfile = UserFile(user_id)
        
        # 生成新的会话ID
        import uuid
        session_id = f"session-{uuid.uuid4()}"
        
        # 创建项目
        new_project_name = userfile.init_project(project_name, session_id, workflow_type)
        
        return {
            "success": True,
            "project_name": new_project_name,
            "session_id": session_id,
            "workflow_type": workflow_type
        }
    except Exception as e:
        return get_error_response(detail=str(e), status_code=500)

if __name__ == "__main__":
    # 启动uvicorn服务器
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8003,
        reload=True  # 开发模式下启用热重载
    )
