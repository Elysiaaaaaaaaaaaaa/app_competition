# 后端API服务接口文档

## 1. 服务概述

后端API服务是一个基于FastAPI框架开发的Web服务，用于前端与后端代理系统的交互。该服务提供了健康检查和主要的工作处理接口，支持多用户、多项目的会话管理。

### 1.1 基本信息

- **服务名称**: 后端API服务
- **版本**: 1.0.0
- **技术栈**: Python 3.10+, FastAPI, Uvicorn
- **默认端口**: 8003
- **当前开发进度**: 正在调试中，仅支持在localhost:8003上运行。

## 2. API端点列表

| 方法 | 路径 | 功能描述 |
|------|------|----------|
| GET | `/` | 根路径健康检查 |
| GET | `/api/v1/health` | API版本化健康检查 |
| POST | `/api/v1/work` | 主要工作处理接口 |

## 3. 详细API说明

### 3.1 根路径健康检查

#### 请求
- **方法**: GET
- **路径**: `/`
- **参数**: 无

#### 响应
```json
{
  "message": "后端服务运行正常",
  "version": "1.0.0"
}
```

### 3.2 API版本化健康检查

#### 请求
- **方法**: GET
- **路径**: `/api/v1/health`
- **参数**: 无

#### 响应
```json
{
  "status": "healthy",
  "service": "backend-api"
}
```

### 3.3 工作处理接口

#### 请求
- **方法**: POST
- **路径**: `/api/v1/work`
- **请求体**: `WorkRequest` 对象

##### 请求模型 (WorkRequest)
```json
{
  "project_name": "string",
  "user_input": "string",
  "user_id": "string",
  "mode": "string"
}
```

| 字段名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| project_name | string | 是 | 项目名称，用于标识不同的项目会话 |
| user_input | string | 是 | 用户输入文本，包含具体的任务需求 |
| user_id | string | 是 | 用户唯一标识符，用于区分不同用户 |
| mode | string | 是 | 运行模式，如'test'表示测试模式 |

#### 响应
```json
{
  "success": true,
  "message": "string",
  "end_session": false,
  "project_name": "string",
  "session_id": "string",
  "session_data": {
    "material": {
      "idea": [],
      "outline": [],
      "screen": [],
      "video_address": []
    },
    "chat_with_assistant": true,
    "modify_request": {
      "outline": null,
      "screen": null
    },
    "modify_num": null,
    "video_generating": 0,
    "editing_screen": null,
    "message_count": 0,
    "now_task": "string",
    "now_state": "string"
  }
}
```

```json
now_task{
  "imagination": "正在与助手构建影片相关的细节，如角色、场景、动作等。最终结果将被添加到session_data.material.idea中。",
  "outline": "正在与助手构建影片的大纲。最终结果将被添加到session_data.material.outline中。",
  "screen": "正在与助手构建影片的剧本。最终结果将被添加到session_data.material.screen中。",
  "video": "正在生成视频。最终结果将被添加到session_data.material.video_address中。"
}
```

```json
now_state{
  "None": "初始状态，等待用户输入。",
  "modify_confirm": "询问用户是否需要修改当前任务的结果。特别的，当now_task为animation时，询问用户是否需要修改当前分镜对应的提示词（即screen）。用户确认修改后需要选择修改的内容索引。",
  "modify": "用户正在与assistant对话，确认修改的具体内容。",
  "create": "用户通过与assistant的对话，确认了idea、modify_request中的内容，即将把这些内容交给各种agent进行生成任务"
}
```

| 字段名 | 类型 | 描述 |
|--------|------|------|
| success | boolean | 请求处理是否成功 |
| message | string | 助手的回复文本 |
| end_session | boolean | 会话是否结束 |
| project_name | string | 项目名称 |
| session_id | string | 会话唯一标识符 |
| session_data | object | 会话详细数据 |
| session_data.material | object | 项目材料数据 |
| session_data.material.idea | array | 创意想法列表 |
| session_data.material.outline | array | 大纲内容 |
| session_data.material.screen | array | 剧本内容 |
| session_data.material.video_address | array | 生成的视频地址列表 |
| session_data.chat_with_assistant | boolean | 是否继续与助手对话 |
| session_data.modify_request | object | 修改请求数据 |
| session_data.video_generating | number | 正在生成的视频索引 |
| session_data.now_task | string | 当前任务类型 |
| session_data.now_state | string | 当前状态 |

#### 错误响应
```json
{
  "detail": "错误描述"
}
```

## 4. 服务架构与工作流程

### 4.1 核心组件

1. **FastAPI应用**: 处理HTTP请求和响应
2. **PersonalAssistantOrchestrator**: 协调各种代理完成任务
3. **UserFile**: 管理用户文件和会话数据
4. **各种代理(Agents)**: 处理具体的业务逻辑
   - Assistant: 助手代理，处理用户对话
   - OutlineWriter: 大纲编写器
   - ScreenWriter: 剧本编写器
   - Animator: 动画生成器

### 4.2 工作流程

1. 客户端发送POST请求到`/api/v1/work`端点
2. API验证请求参数并创建WorkRequest对象
3. 初始化PersonalAssistantOrchestrator实例
4. 调用handle_user_input方法处理用户输入
5. 根据用户输入和当前会话状态，路由到相应的处理节点
6. 调用相应的代理完成具体任务
7. 保存会话数据和项目内容
8. 返回处理结果给客户端

## 5. 会话管理

- 每个用户可以创建多个项目
- 每个项目有独立的会话ID
- 会话数据包括任务状态、材料内容和进度信息
- 会话数据会自动保存到用户文件系统

## 6. 错误处理

- API使用HTTP状态码表示错误类型
- 500: 服务器内部错误
- 400: 请求参数错误
- 所有错误都会返回包含错误描述的JSON响应

## 7. 开发与测试

### 7.1 启动服务

```bash
python app.py
```

### 7.2 测试模式

在请求中设置`mode=test`可以启用测试模式，跳过实际的代理调用，返回模拟结果。

## 8. 接口示例

### 8.1 健康检查示例

```bash
curl http://localhost:8003/
```

响应：
```json
{
  "message": "后端服务运行正常",
  "version": "1.0.0"
}
```

### 8.2 工作处理示例

```bash
curl -X POST "http://localhost:8003/api/v1/work" \
  -H "Content-Type: application/json" \
  -d '{"project_name": "test_project", "user_input": "帮我写一个关于太空探索的故事大纲", "user_id": "user_123", "mode": "test"}'
```

响应：
```json
{
  "success": true,
  "message": "call outline",
  "end_session": false,
  "project_name": "test_project",
  "session_id": "session-12345678-1234-5678-1234-567812345678",
  "session_data": {
    "material": {
      "idea": [],
      "outline": [],
      "screen": [],
      "video_address": []
    },
    "chat_with_assistant": true,
    "modify_request": {
      "outline": null,
      "screen": null
    },
    "modify_num": null,
    "video_generating": 0,
    "editing_screen": null,
    "message_count": 0,
    "now_task": "imagination",
    "now_state": "None"
  }
}
```

## 9. 版本历史

- **1.0.0** (初始版本)
  - 实现了根路径健康检查
  - 实现了API版本化健康检查
  - 实现了主要工作处理接口
  - 支持多用户、多项目会话管理
  - 支持测试模式
