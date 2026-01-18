# 实现Orch\_with\_graph类

## 1. 设计思路

* 保留原有的`ChatGraphState`状态定义，包含会话ID、用户输入、会话数据、当前状态和回复

* 构建完整的LangGraph状态图，包含以下节点：

  * `assistant`：处理用户交互和任务调度

  * `outline_writer`：生成大纲

  * `screen_writer`：生成分镜

  * `animator`：生成动画

  * `intend`：询问用户是否需要修改

  * `modify`：处理用户修改请求

* 使用LangGraph的条件路由来管理状态流转，替代原有的`route_state`和`route_task`方法

* 保留原有的业务逻辑，将状态管理和路由交给LangGraph

## 2. 实现步骤

1. 复制原有的`PersonalAssistantOrchestrator`类，创建`Orch_with_graph`类
2. 重新实现`_build_graph`方法，构建完整的状态图
3. 实现`intend`节点，用于询问用户是否需要修改
4. 实现条件路由函数，管理节点间的流转
5. 修改`handle_user_input`方法，简化逻辑，主要依赖LangGraph的状态管理
6. 测试新类的功能，确保与原有类功能一致

## 3. 状态流转设计

```
assistant → outline_writer → intend → ┬→ modify → assistant
                                      └→ screen_writer → intend → ┬→ modify → assistant
                                                                   └→ animator → intend → ┬→ modify → assistant
                                                                                           └→ END
```

## 4. 关键改进

* 使用LangGraph的状态图管理整个工作流，更直观、易扩展

* 将intend功能整合到图中，避免了原有的input交互，更适合后续前端集成

* 条件路由基于状态自动判断，不需要手动调用`route_state`和`route_task`

* 新增节点时，只需要添加节点函数和路由规则，不需要修改大量代码

## 5. 代码结构

```python
class Orch_with_graph:
    def __init__(self, clients: Dict[str, AipRpcClient], userfile: UserFile):
        # 保留原有初始化逻辑
        self._graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        # 构建完整的LangGraph状态图
        pass
    
    def assistant_node(self, state: ChatGraphState) -> ChatGraphState:
        # 处理用户交互
        pass
    
    def outline_writer_node(self, state: ChatGraphState) -> ChatGraphState:
        # 生成大纲
        pass
    
    def screen_writer_node(self, state: ChatGraphState) -> ChatGraphState:
        # 生成分镜
        pass
    
    def animator_node(self, state: ChatGraphState) -> ChatGraphState:
        # 生成动画
        pass
    
    def intend_node(self, state: ChatGraphState) -> ChatGraphState:
        # 询问用户是否需要修改
        pass
    
    def modify_node(self, state: ChatGraphState) -> ChatGraphState:
        # 处理用户修改请求
        pass
    
    def route_after_intend(self, state: ChatGraphState) -> str:
        # 处理intend后的路由
        pass
    
    async def handle_user_input(self, session_id: str) -> AssistantReply:
        # 简化的主入口，依赖LangGraph状态管理
        pass

    def acps_call_agents(self,session_data):
        #模仿原有的方法使用AgentRegisty通过acps协议call agent
        pass
```

