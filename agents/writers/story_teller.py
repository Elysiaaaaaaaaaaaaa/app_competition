'''
story board创作智能体，会接收到三个任务：
创作背景图片生成提示词，类型为t2i提示词
创作主体形象图片生成提示词，类型为t2i提示词
根据前两个任务的结果，创作分镜首帧图片生成提示词，类型为i2i提示词
接收到的任务类型可以在session_data的now_task字段里获取
'''

from volcenginesdkarkruntime import Ark
import time

# 主体描述示例
subject_example = f'''## 主体描述 1
**镜号：** 1
**主体：** 库珀

### 视觉特征
- **外貌：** 中年男性，坚毅的面孔，眼神专注，短发，穿着太空服
- **动作：** 双手操控飞船操纵杆，身体微微前倾，注意力集中
- **表情：** 严肃、专注，带有一丝紧张
- **细节：** 太空服上有磨损痕迹，头盔放在旁边，手指关节因用力而发白

### 情绪与性格
- **情绪：** 紧张、责任感强
- **性格：** 果断、专业、有领导力

### 关键动作
- 操控飞船操纵杆
- 观察仪表盘数据
- 与船员交流

---
## 主体描述 2
**镜号：** 2
**主体：** 机器人凯斯

### 视觉特征
- **外貌：** 多段式机械臂，银色金属外壳，蓝色LED指示灯
- **动作：** 变形为多足形态，机械臂精准操作，移动平稳
- **细节：** 机械臂关节灵活，外壳有轻微划痕，底部有防滑设计

### 功能与角色
- **功能：** 数据采集、环境探测、机械操作
- **角色：** 辅助船员，提供技术支持

### 关键动作
- 变形为多足形态
- 从海水中捞起信号信标
- 跟随船员行进

---
'''

# 背景描述示例
background_example = f'''## 背景描述 1
**镜号：** 1
**背景：** 米勒星球海洋与天空

### 视觉特征
- **环境：** 无垠的平静浅海，海面泛着微光，厚重的云层在头顶翻滚
- **色彩：** 深海蓝为主色调，天空呈现灰蓝色，远处有黑洞投射的微弱引力光晕
- **光线：** 云层散射的自然光，黑洞边缘的微弱光晕
- **氛围：** 神秘、壮丽，带有一丝压迫感

### 关键元素
- 黑洞引力光晕
- 厚重的云层
- 平静的浅海
- 远处的地平线

### 空间关系
- 飞船在云层下方飞行，逐渐接近海面
- 黑洞位于画面远处，散发着微弱的光晕
- 海面与天空形成清晰的分界线

---
## 背景描述 2
**镜号：** 2
**背景：** 米勒飞船残骸现场

### 视觉特征
- **环境：** 浅海区域，海水清澈，能够看到海底的岩石
- **色彩：** 海水蓝绿色，飞船残骸呈现锈蚀的棕色，天空灰蓝色
- **光线：** 自然光线，云层散射光
- **氛围：** 荒凉、破败，带有探索的神秘感

### 关键元素
- 半浸在海水中的飞船残骸
- 散落的管道和仪器零件
- 远处的"山峦"轮廓
- 浅海底部的岩石

### 空间关系
- 船员站在残骸前方
- 远处的"山峦"在海平面上形成清晰轮廓
- 飞船残骸向远处延伸

---
'''

# 初始化Ark客户端
client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key='c96dbd1f-aeab-461c-90d6-8096b0baeecd',
)

class StoryTeller:
    def __init__(self, name, download_link):
        self.storyboards = []
        self.name = name
        self.download_link = f'{download_link}/{self.name}'
        self.last_id = None
    
    def init_assistant(self, message, task_type):
        """
        创建初始对话，根据任务类型选择不同的prompt和示例
        :param message: 用户需求
        :param task_type: 任务类型，'subject'表示主体描述，'background'表示背景描述
        :return: 生成的内容
        """
        if task_type == 'subject':
            prompt = f"你是一个专业的故事板 writer，你的任务是根据用户提供的分镜大纲生成详细的主体描述。\n主体描述需要包含以下要素：\n1. 镜号、主体名称\n2. 视觉特征：外貌、动作、表情、细节\n3. 情绪与性格（如果是人物）或功能与角色（如果是物体/机器人）\n4. 关键动作\n\n主体描述的格式必须严格按照以下示例：\n{subject_example}"
        elif task_type == 'background':
            prompt = f"你是一个专业的故事板 writer，你的任务是根据用户提供的分镜大纲生成详细的背景描述。\n背景描述需要包含以下要素：\n1. 镜号、背景场景\n2. 视觉特征：环境、色彩、光线、氛围\n3. 关键元素\n4. 空间关系\n\n背景描述的格式必须严格按照以下示例：\n{background_example}"
        else:
            # 默认生成完整故事板
            prompt = f"你是一个专业的故事板 writer，你的任务是根据用户提供的分镜大纲生成详细的故事板。\n故事板需要包含视觉描述、情绪与节奏、关键元素等。"
        
        completion = client.responses.create(
            model="doubao-seed-1-6-251015",
            input=[
                {
                    'role':'system',
                    'content': prompt
                },
                {
                    'role':'user',
                    'content': message
                }
            ],
            caching={"type": "enabled"}, 
            thinking={"type": "disabled"},
            expire_at=int(time.time()) + 360
        )
        self.last_id = completion.id
        return completion.output[-1].content[0].text
    
    def call(self, session_data: dict) -> str:
        """
        向火山方舟平台发送请求并返回内容
        :param session_data: 包含创作需求或修改请求的数据，其中now_task指定任务类型
        :return: 生成的故事板
        """
        # 确定任务类型
        if 'now_task' in session_data:
            now_task = session_data['now_task']
            if now_task == '主体':
                task_type = 'subject'
            elif now_task == '背景':
                task_type = 'background'
            else:
                # 默认生成完整故事板
                task_type = 'full'
        else:
            task_type = 'full'
        
        if not self.last_id:
            # 初始创作
            if 'outline' in session_data:
                outline = '\n'.join(session_data['outline'])
            else:
                outline = ''.join(session_data['material']['outline'])
            
            if task_type == 'full':
                # 生成完整故事板（兼容原有功能）
                prompt = f"你是一个专业的故事板 writer，你的任务是根据用户提供的分镜大纲生成详细的故事板。"
                completion = client.responses.create(
                    model="doubao-seed-1-6-251015",
                    input=[
                        {
                            'role':'system',
                            'content': prompt
                        },
                        {
                            'role':'user',
                            'content': outline
                        }
                    ],
                    caching={"type": "enabled"}, 
                    thinking={"type": "disabled"},
                    expire_at=int(time.time()) + 360
                )
                self.last_id = completion.id
                raw_story = completion.output[-1].content[0].text
            else:
                # 根据任务类型生成主体或背景描述
                raw_story = self.init_assistant(outline, task_type)
            
            self.storyboards = raw_story.split('---')
            return self.storyboards
        
        # 修改请求
        completion = client.responses.create(
            model="doubao-seed-1-6-251015",
            previous_response_id = self.last_id,
            input=[
                {
                    'role':'system',
                    'content':f"你是一个专业的故事板 writer，现在请根据用户的修改请求，修改你之前写的{'主体描述' if task_type == 'subject' else '背景描述' if task_type == 'background' else '故事板'}。\n{'主体描述' if task_type == 'subject' else '背景描述' if task_type == 'background' else '故事板'}如下：\n{self.storyboards}"
                },
                {
                    'role':'user',
                    'content':str(session_data['modify_request']['story'])
                }
            ],
            caching={"type": "enabled"}, 
            thinking={"type": "disabled"},
            expire_at=int(time.time()) + 360
        )
        self.last_id = completion.id
        raw_story = completion.output[-1].content[0].text
        self.storyboards = raw_story.split('---')
        return self.storyboards
