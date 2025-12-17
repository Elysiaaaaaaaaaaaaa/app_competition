"""
A2A协议相关的常量和类型定义
"""
from typing import Dict, List, Any, Optional
from enum import Enum

# 默认超时设置
DEFAULT_TIMEOUT = 30.0
LONG_TIMEOUT = 180.0
POLL_TIMEOUT = 30.0

# 轮询设置
DEFAULT_POLL_INTERVAL = 2.0
MAX_POLL_ATTEMPTS = 60
MAX_RETRIES = 3

# JSON-RPC方法
class RPCMethods(str, Enum):
    SEND_MESSAGE = "message/send"
    GET_TASK = "tasks/get"  # 修正：使用复数形式 tasks/get
    CANCEL_TASK = "tasks/cancel"

# 任务状态
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

# 构建消息请求
def build_message_request(message: str, context_id: str = None, message_id: str = None) -> Dict[str, Any]:
    """构建符合A2A协议的消息请求"""
    from uuid import uuid4
    
    if not context_id:
        context_id = str(uuid4())
    if not message_id:
        message_id = str(uuid4())
    
    return {
        "jsonrpc": "2.0",
        "id": str(uuid4()),
        "method": RPCMethods.SEND_MESSAGE,
        "params": {
            "message": {
                "messageId": message_id,
                "contextId": context_id,
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": message
                    }
                ]
            },
            "configuration": {
                "acceptedOutputModes": ["text", "text/plain", "image/png"]
            }
        }
    }

# 构建任务查询请求
def build_task_request(task_id: str) -> Dict[str, Any]:
    """构建符合A2A协议的任务查询请求"""
    from uuid import uuid4
    
    return {
        "jsonrpc": "2.0",
        "id": str(uuid4()),
        "method": RPCMethods.GET_TASK,  # 确保使用正确的枚举值
        "params": {
            "id": task_id
        }
    }
