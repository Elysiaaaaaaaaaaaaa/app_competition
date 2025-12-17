from pydantic import BaseModel
from typing import Dict, Any
class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 请求基类"""
    jsonrpc: str = "2.0"
    id: str
    method: str
    params: Dict[str, Any]

class GetTaskRequest(JSONRPCRequest):
    """获取任务状态请求"""
    method: str = "tasks/get"  # 修正：使用tasks/get而不是task/get
    params: Dict[str, Any]


