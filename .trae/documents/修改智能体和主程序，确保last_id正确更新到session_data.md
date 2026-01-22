## 问题分析
在当前实现中，智能体内部修改session_data不会对主程序产生影响，因为：
1. 智能体的call方法只返回处理结果（如文本、大纲等）
2. 主程序只使用这些结果更新state，没有更新session_data中的last_id字段
3. 每次前端API调用都会初始化新的工作流对象，导致last_id丢失

## 解决方案
修改智能体和主程序，让智能体返回包含结果和last_id的信息，然后在主程序中显式更新state的session_data字段。

## 具体修改步骤

### 1. 修改Assistant类
- 修改`call`方法，返回包含文本结果和last_id的元组
- 修改`next_call`方法，确保正确更新last_id

### 2. 修改OutlineWriter类
- 修改`call`方法，返回包含大纲结果和last_id的元组

### 3. 修改ScreenWriter类
- 修改`call`方法，返回包含分镜结果和last_id的元组

### 4. 修改主程序（run_acps.py）
- 在调用Assistant.call后，更新state['session_data']['last_id']['assistant']
- 在调用OutlineWriter.call后，更新state['session_data']['last_id']['outline_writer']
- 在调用ScreenWriter.call后，更新state['session_data']['last_id']['screen_writer']

### 5. 修改相关调用点
- 更新所有调用智能体call方法的地方，处理新的返回值格式

## 预期效果
- 每次智能体调用后，last_id都会被正确保存到session_data中
- 前端API调用时，即使初始化新的工作流对象，也能从session_data中获取到之前的last_id
- 保持对话上下文的连续性，提高大模型对话质量

## 风险评估
- 修改量较大，需要更新多个文件和方法
- 需要确保所有调用点都正确处理新的返回值格式
- 可能会影响现有功能，需要进行全面测试

## 实施顺序
1. 先修改智能体类，让它们返回包含last_id的元组
2. 再修改主程序，处理新的返回值格式并更新session_data
3. 最后运行测试，确保功能正常