from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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

# 添加CORS中间件，允许前端跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源，生产环境应指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加静态文件服务，用于提供视频文件访问
# 注意：这需要确保user_files目录存在
if os.path.exists("./user_files"):
    app.mount("/videos", StaticFiles(directory="./user_files", html=False), name="videos")

# 添加static目录的静态文件服务，用于提供占位符视频
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

# 确保占位符视频文件存在，如果不存在则创建
placeholder_path = os.path.join(static_dir, "placeholder.mp4")
if not os.path.exists(placeholder_path):
    print(f"Placeholder video not found at: {placeholder_path}")
    print("Attempting to copy from frontend test video...")
    
    # 尝试从前端目录复制测试视频（多种可能的路径）
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.dirname(current_file_dir)  # 假设app.py在app_competition-master目录下
    
    frontend_video_paths = [
        # 相对路径尝试
        os.path.join(current_file_dir, "..", "Nexus-main", "Nexus-main", "src", "assets", "test1.mp4"),
        os.path.join(current_file_dir, "..", "..", "Nexus-main", "Nexus-main", "src", "assets", "test1.mp4"),
        # 从工作区根目录尝试
        os.path.join(workspace_root, "Nexus-main", "Nexus-main", "src", "assets", "test1.mp4"),
        # 绝对路径尝试（基于当前文件位置）
        os.path.join(os.path.dirname(current_file_dir), "Nexus-main", "Nexus-main", "src", "assets", "test1.mp4"),
    ]
    
    copied = False
    for frontend_path in frontend_video_paths:
        abs_path = os.path.abspath(frontend_path)
        print(f"  Trying: {abs_path}")
        if os.path.exists(abs_path):
            try:
                import shutil
                shutil.copy2(abs_path, placeholder_path)
                file_size = os.path.getsize(placeholder_path)
                print(f"[OK] Successfully copied placeholder video from: {abs_path}")
                print(f"  File size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
                copied = True
                break
            except Exception as e:
                print(f"  [ERROR] Could not copy from {abs_path}: {e}")
    
    # 如果复制失败，创建一个最小的有效MP4文件（但警告用户）
    if not copied:
        print("[WARNING] Could not find frontend test video. Creating minimal placeholder...")
        print("  Note: Minimal video may not play in browsers. Please manually copy a video file.")
        minimal_mp4 = bytes([
            0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,  # ftyp box
            0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,
            0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,
            0x61, 0x76, 0x63, 0x31, 0x6D, 0x70, 0x34, 0x31,
            0x00, 0x00, 0x00, 0x08, 0x6D, 0x64, 0x61, 0x74,  # mdat box (empty)
            0x00, 0x00, 0x00, 0x00
        ])
        try:
            with open(placeholder_path, "wb") as f:
                f.write(minimal_mp4)
            print(f"  Created minimal placeholder video: {placeholder_path}")
            print("  [WARNING] This minimal video may not play in all browsers.")
            print("  [TIP] To fix: Copy Nexus-main/Nexus-main/src/assets/test1.mp4 to app_competition-master/static/placeholder.mp4")
        except Exception as e:
            print(f"  [ERROR] Could not create placeholder video: {e}")
else:
    # 文件已存在，检查文件大小
    file_size = os.path.getsize(placeholder_path)
    if file_size < 1000:  # 小于1KB可能是无效文件
        print(f"[WARNING] Placeholder video exists but is very small ({file_size} bytes).")
        print("  Consider replacing it with a real video file.")
    else:
        print(f"[OK] Placeholder video found: {placeholder_path} ({file_size / 1024 / 1024:.2f} MB)")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir, html=False), name="static")


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
    video_duration: int = None  # 视频时长（秒），可选，默认使用后端配置

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

@app.get("/api/v1/test-video-placeholder")
async def test_video_placeholder():
    """
    返回占位符视频文件
    用于测试模式下显示视频已生成
    如果static目录下的文件不存在，返回重定向到静态文件服务
    """
    from fastapi.responses import FileResponse, RedirectResponse
    
    # 优先使用static目录下的占位符视频
    placeholder_path = os.path.join(os.path.dirname(__file__), "static", "placeholder.mp4")
    
    if os.path.exists(placeholder_path):
        return FileResponse(
            placeholder_path,
            media_type="video/mp4",
            headers={
                "Cache-Control": "public, max-age=3600"
            }
        )
    else:
        # 如果占位符文件不存在，重定向到静态文件服务
        # 或者返回一个可用的测试视频URL
        # 这里返回静态文件服务的URL，前端可以通过这个URL访问
        return RedirectResponse(
            url="/static/placeholder.mp4",
            status_code=307  # 临时重定向
        )


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
        mode = request.mode
        userfile = UserFile(user)
        print(user)
        # 创建Text2VideoWorkflow实例
        orchestrator = Text2VideoWorkflow(clients=None, userfile=userfile, project_name=project_name, mode=mode)
        
        # 如果请求中包含video_duration，设置到session_data中
        if request.video_duration is not None:
            session_data = orchestrator._get_session_state(orchestrator.main_session_id)
            session_data['video_duration'] = request.video_duration
            orchestrator._sessions[orchestrator.main_session_id] = session_data
        
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
        
        # 获取项目的session_id
        project_content = userfile.load_content(project_name)
        session_id = project_content.get('session_id')
        
        # 从session_history中获取最新的session_data
        session_data = None
        if session_id:
            all_sessions = userfile.load_session()
            session_data = all_sessions.get(session_id, {})
        
        return {
            "success": True,
            "chat_history": chat_history,
            "session_data": session_data
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
