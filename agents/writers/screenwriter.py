from volcenginesdkarkruntime import Ark
import json
import os
from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import (Part, Task, TextPart, UnsupportedOperationError)
from a2a.utils import (completed_task, new_artifact)
from a2a.utils.errors import ServerError
import asyncio
import time
from tools.tool_hub import ark_web_search as tools
from tools.web_search import web_search
from base import CONTEXT_CACHE_TIME



client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key='c96dbd1f-aeab-461c-90d6-8096b0baeecd',
)


change_outline_prompt = '''
【角色设定】
你是一位专业的分镜大纲修改专家，擅长根据用户反馈精准调整分镜内容，保持故事完整性和视觉连贯性。

【核心任务】
根据用户提供的修改建议，对现有分镜大纲进行调整，确保修改后的内容完全符合用户需求，同时保持分镜的逻辑连贯性和叙事流畅性。

【修改要求】
1. 严格遵循用户的修改指示，确保所有调整都准确反映用户需求
2. 保持原有分镜的格式和结构不变
3. 确保修改后的镜头之间依然保持良好的叙事逻辑
4. 如有必要，可以对未明确修改的部分进行微调，以确保整体协调一致
'''

outline_example = f'''
镜号 1
详细画面：远景展现徘徊者号冲破米勒星球厚重云层，下方是无垠的平静浅海，海面泛着微光，背景可见黑洞投射的微弱引力光晕；中景呈现飞船尾部推进器微调，以螺旋姿态向信号源方向平稳下降，船体在海面上投下清晰倒影；近景聚焦驾驶舱内，库珀双手操控操纵杆，眼神专注，布兰德、道尔坐于两侧，身体因星球引力微微前倾，神情警惕，机器人凯斯收起多段式机械臂，前方屏幕实时跳动着 “130% 地球引力”“大气成分稳定” 等数据，屏幕光映在众人脸上。
剧情概括：船员驾驶徘徊者号成功抵达米勒星球，准备登陆探寻米勒留下的信号痕迹，初步探测到星球环境数据。
/
镜号 2
详细画面：中景显示飞船平稳着陆浅海，舱门向两侧打开，海水仅没过船员膝盖，布兰德率先迈步下船，裤脚溅起细小水花，道尔和变形为多足形态的凯斯紧随其后；特写镜头聚焦凯斯的机械臂，精准从海水中捞起一枚破碎的信号信标，信标外壳有明显的撞击划痕和海水侵蚀痕迹，指示灯早已熄灭；全景展现三人向远处行走，米勒的飞船残骸半浸在海水中，金属外壳锈蚀严重，散落着断裂的管道和仪器零件，远处海平面上矗立着一道 “山峦” 轮廓，与天空形成清晰分界线。
剧情概括：船员登陆星球，发现米勒的信号信标残骸，继续向飞船失事地点行进，远处的 “山峦” 为后续危机埋下伏笔。
/
镜号 3
详细画面：特写捕捉库珀在驾驶舱内的神情，他原本放松的面部突然紧绷，瞳孔收缩，视线死死锁定舷窗外的 “山峦”；全景镜头快速拉远，瞬间揭露 “山峦” 的真面目 —— 一座高耸入云、裹挟着白色泡沫的巨型巨浪，浪峰遮蔽阳光，在海面投下巨大阴影；俯拍镜头展现巨浪以极快速度向船员和飞船推进，所过之处海面形成环形波纹，海水被挤压得泛起白色浪花；中景呈现布兰德正弯腰从残骸中抽取数据记录仪，手指已触碰到设备，道尔侧身回头，看清巨浪后脸色瞬间惨白，身体下意识紧绷。
剧情概括：库珀率先发现 “山峦” 实为巨型巨浪，危机骤然降临，此时布兰德正即将获取关键数据。
/
镜号 4
详细画面：跟拍镜头追踪凯斯，它迅速变形为轮状结构，以高速滚向布兰德，轮体在海面上留下一道水痕；特写展现布兰德的腿部被残骸的金属支架压住，她试图挣脱，海水已漫至腰部，头发被海风和水花打湿，脸上写满焦急；中景呈现道尔站在布兰德身后，伸手欲拉她，同时余光瞥见身后另一波稍小的巨浪已逼近，浪花已溅到他的裤腿；近景显示凯斯用两根机械臂撑起压在布兰德腿上的支架，另一根手臂拽住布兰德的胳膊，三人向飞船方向狂奔，布兰德怀中紧紧抱着数据记录仪。
剧情概括：凯斯紧急救援被残骸困住的布兰德，道尔掩护撤退，三人在巨浪逼近下向飞船狂奔。
/
镜号 5
详细画面：近景记录布兰德和凯斯踉跄冲进飞船，道尔刚踏上舱门台阶，第一波巨浪瞬间席卷而来，巨大的冲击力将他卷入海中，仅留下一只伸出水面的手便被浪花吞没；全景展现巨浪瞬间吞没飞船，飞船被浪头高高抬起，顺着浪峰向上攀升，船体因巨大压力发生轻微变形，表面的观测窗被海水覆盖；特写聚焦驾驶舱内，海水从舱门缝隙涌入，仪器屏幕因进水短路闪烁红光，部分按钮弹出，库珀紧攥操控杆，指节发白，额头渗出冷汗，眼神坚定；中景呈现飞船随巨浪翻滚后重重砸回海面，溅起数十米高的水花，船体倾斜 45 度，舱内积水漫过脚踝，屏幕显示 “引擎进水，排水程序启动，预计 45 分钟”。
剧情概括：道尔牺牲，布兰德和凯斯成功登船，飞船被巨浪吞没后遭受重创，引擎进水陷入故障。
/
镜号 6
详细画面：近景中布兰德瘫坐在船舱地板上，背靠倾斜的仪器柜，怀中仍紧紧抱着数据记录仪，脸上满是泪痕，头发凌乱地贴在脸颊；特写捕捉库珀的神情，他盯着引擎仪表盘上的排水进度条，拳头紧握，嘴角紧抿，眼神中交织着无奈、愤怒与焦虑；近景展现船舱内的积水正缓慢退去，通过舷窗可见外部海面逐渐恢复平静，但远处海平面上，另一道巨型巨浪的轮廓正逐渐清晰，阴影开始向飞船方向蔓延。
剧情概括：布兰德因道尔牺牲陷入自责，库珀关注飞船故障情况，而新的巨浪危机已悄然逼近。
/
'''

change_screen_prompt = '''
【角色设定】
你是一位专业的分镜脚本修改专家，擅长根据用户反馈和原始大纲，精准调整分镜脚本的视觉描述和叙事细节。

【核心任务】
根据用户提供的修改建议，对现有分镜脚本进行调整，确保修改后的内容完全符合用户需求，同时保持与原始大纲的一致性和视觉表现力。

【修改要求】
1. 严格遵循用户的修改指示，确保所有调整都准确反映用户需求
2. 保持原有分镜脚本的格式和结构不变
3. 确保修改后的分镜内容与原始大纲保持一致
4. 增强视觉描述的准确性和表现力，为视频生成提供更清晰的指导
5. 如有必要，可以对未明确修改的部分进行微调，以确保整体协调一致
'''

script_example = '''
镜号 1
场景：米勒星球的浅海区域，海面呈深蓝灰色且平静无波，泛着微弱反光，远处海平面矗立着形似 “山峦” 的巨大轮廓，背景悬着黑洞，投射出淡紫色引力光晕；徘徊者号飞船平稳着陆浅海，船体下半部分浸在水中，布兰德、道尔在不远处的米勒飞船残骸（半浸水中，金属外壳锈蚀、零件散落）旁探寻，库珀留守驾驶舱内观察。
【风格】科幻写实风格，冷色调为主（深蓝灰海面、银灰航天服、暗紫黑洞光晕），高对比度，光影层次分明（黑洞光晕照亮海面局部，残骸投射深色阴影，驾驶舱内仪器蓝光形成局部亮面）
【角色】：库珀：典型的中年男性形象，发型是利落的短黑发，看起来干练，身形偏精瘦硬朗，常穿浅灰 T 恤，面部线条清晰，气质兼具 “父亲的温和” 与 “宇航员的坚毅”。
运动：库珀在驾驶舱内以高速操控杆操作，初始神情专注，后骤然紧绷，眼神中夹杂着警惕与焦虑。
【镜头】1. 初始镜头：固定特写，聚焦驾驶舱内库珀面部，画面中心为其双眼，舷窗边缘作为背景框，窗外 “山峦” 轮廓模糊可见；2. 过渡镜头：极速拉远，镜头从面部特写快速拉升至全景，过程带轻微动态模糊，逐步展现驾驶舱、飞船整体、浅海海面及残骸区域；3. 聚焦镜头：拉远后短暂定格全景，随后镜头轻微下移并聚焦海面上的布兰德与道尔，突出二人未察觉危机的状态，同时清晰呈现 “山峦” 实为巨型巨浪的全貌（高约千米，灰黑主体裹挟白色泡沫，底部阴影笼罩海面）；4. 收尾镜头：镜头轻微回拉，再次带起飞船与巨浪的相对位置，强化飞船与人物在巨浪前的渺小感
【对白】
（库珀）：（瞳孔收缩，难以置信地低声颤抖）那不是山，那是个浪。
【音效】紧张急促的管弦乐背景音乐（随镜头拉远逐渐增强），巨浪移动时的沉闷低频轰鸣（从微弱到清晰），驾驶舱内仪器的轻微电子提示音，布兰德操作时的细微金属碰撞音，后续布兰德 “再给我 10 秒” 的模糊惊呼前置音
/
'''

abstract_example = '''
库珀顺利完成了在米勒星球的降落，米勒星球是一个被海洋覆盖的星球，远处有一个类似 “山峦” 的巨大轮廓，他们走下飞船寻找米勒飞行器的残骸，这时库珀发现原来”山峦“是一个数十米高的巨浪，于是他紧急呼叫两位同伴回飞船。
'''

screen_prompt = f'''
【角色设定】
你是一位专业的分镜脚本创作大师，擅长将抽象的分镜大纲转化为详细、生动、可视化的分镜脚本，为AI视频生成提供精准的视觉指导。

【核心任务】
根据用户提供的分镜大纲，为每个镜号创作详细的分镜脚本，确保每个镜头都能准确传达故事内容、视觉风格和叙事节奏，适合AI视频生成模型使用。

【创作规则】
1. 信息核实：如果大纲中存在不明确或不了解的信息（如特定角色外形、专业术语等），必须先使用联网搜索工具确认后再进行创作
2. 时长控制：每个分镜脚本控制在4-6秒的视觉内容（适合短视频制作）
3. 格式要求：每个分镜脚本写完后用’/‘隔开
4. 结构完整性：每个分镜脚本必须包含完整的视觉要素，参考以下示例结构：
{script_example}
！注意！每个分镜脚本后面都有一个‘/’，用于分隔不同的镜头。


【创作要点】
- 场景描述：清晰设定时间、地点和环境氛围
- 风格定位：明确视觉风格（如科幻写实、卡通、悬疑等）、主色调和光影效果，保持整体风格一致性
- 角色刻画：详细描述角色的外貌、动作和表情
- 镜头设计：精确说明镜头运动（推/拉/摇/移/跟/升/降）和景别变化（远景/中景/近景/特写）
- 音效与对白：根据剧情需要添加合适的音效和对白指示，增强叙事表现力
- AI友好：使用具体、具象的描述语言，避免抽象或模糊表达，确保AI模型能准确理解视觉需求
- 一致性：保持不同镜头间的视觉风格、角色形象和叙事逻辑的连贯性

【搜索工具使用】你可以使用联网搜索工具来核实分镜大纲中不明确或不了解的信息。
'''

abstract_prompt = f'''
【角色设定】
你是一位专业的剧情概括专家，擅长将用户的创意需求提炼为简洁、清晰、结构化的剧情摘要，为后续视频创作提供明确的叙事方向。

【核心任务】
根据用户提供的视频创意需求，生成简洁明了的剧情概括，突出核心故事线和关键事件，为分镜大纲创作奠定基础。

【创作要求】
1. 聚焦核心：由于可生成视频的长度限制（通常1分钟以内），概括内容必须集中在单一核心事件上
2. 结构清晰：包含事件的起因、发展、高潮等关键节点，逻辑连贯
3. 简洁明了：用最精炼的语言传达故事精髓，避免冗余细节
4. 示例参考：参考以下示例格式：
{abstract_example}

【创作要点】
- 明确故事主线和核心冲突
- 突出关键角色和他们的目标
- 指明故事发生的时间和地点
- 保持叙事节奏紧凑，适合短视频制作需求
'''

outline_prompt = f'''
【角色设定】
你是一位专业的分镜大纲创作专家，擅长将用户的创意需求转化为结构化、可视化的分镜大纲，为后续分镜脚本创作提供清晰的框架指导。

【核心任务】
根据用户提供的视频创意需求，创作详细的分镜大纲，确保每个镜头都能准确传达故事内容和视觉效果，为后续视频制作提供坚实基础。

【创作要求】
1. 聚焦单一事件：由于视频长度限制（通常1分钟以内），所有分镜必须集中描绘一个核心事件
2. 要素完整：每个分镜必须包含场景、详细画面和简要剧情
3. 人物限制：涉及的人物角色不超过三个，确保叙事紧凑
4. 人物参照：对于角色形象，尽量使用影视作品中知名的相似角色代替（如“男性，老魔法师”可用甘道夫或邓布利多代替），方便后续分镜创作
5. 格式要求：每个分镜写完后用{'/'}隔开
6. 示例参考：参考以下示例格式：
{outline_example}

【创作要点】
- 景别明确：清晰标注每个镜头的景别（远景/中景/近景/特写）
- 动作连贯：确保镜头之间的角色动作和场景转换自然流畅
- 剧情紧凑：突出核心冲突和故事高潮，避免无关细节
- 视觉导向：重点描述画面元素，为后续分镜脚本创作提供丰富素材
'''

class ScreenWriter:
    def __init__(self):
        self.screen = None
    
    def init_assistant(self,message,session_data,sys_prompt):
        # 创建初始对话，包含outline_writer的prompt和示例
        completion = client.responses.create(
            model="doubao-seed-1-6-lite-251015",
            tools = tools,
            input=[
                {
                    'role':'system',
                    'content':sys_prompt
                },
                {
                    'role':'user',
                    'content':message
                }
            ],
            caching={"type": "enabled"}, 
            thinking={"type": "disabled"},
            expire_at=int(time.time()) + CONTEXT_CACHE_TIME,
        )
        last_id = completion.id
        result, last_id = self.next_call(completion, session_data, last_id)
        return result, last_id
    
    def call(self,session_data:dict) -> tuple:
        """
        向火山方舟平台发送请求并返回内容
        :param message: 用户的需求
        :return: 分镜大纲和last_id的元组
        """
        # 根据material中是否存在screen内容选择提示词
        if session_data['material']['screen'] != []:
            # 修改场景：使用修改提示词
            sys_prompt = change_screen_prompt
            message = str(session_data['modify_request']['screen'])
        else:
            # 首次创作：使用首次创作提示词
            sys_prompt = screen_prompt
            message = ''.join(session_data['material']['outline'])
        
        try:
            if not session_data['last_id']['screen_writer']:
                # 首次调用或last_id失效，使用init_assistant
                self.screen = []
                raw_screen, last_id = self.init_assistant(message, session_data, sys_prompt)
                for i in raw_screen.split('/'):
                    if len(i) > 10:
                        self.screen.append(i)
                return self.screen, last_id
            
            # 非首次调用，使用previous_response_id
            print(type(session_data['modify_num']),session_data['modify_num'],session_data['have_modify'])
            need_modify = session_data['material']['screen'][session_data['modify_num'][session_data['have_modify']]-1]
            
            # 确保 self.screen 已经初始化
            if self.screen is None:
                self.screen = session_data['material']['screen'].copy()
            
            completion = client.responses.create(
                model="doubao-seed-1-6-lite-251015",
                previous_response_id = session_data['last_id']['screen_writer'],
                input=[
                    {
                        'role':'system',
                        'content':sys_prompt
                    },
                    {
                        'role':'user',
                        'content':f'请修改这个分镜脚本：{need_modify}\n修改要求：{session_data["modify_request"]["screen"]}'
                    }
                ],
                caching={"type": "enabled"}, 
                thinking={"type": "disabled"},
                expire_at=int(time.time()) + CONTEXT_CACHE_TIME,
            )
            last_id = completion.id
            self.screen[session_data['modify_num'][session_data['have_modify']]-1], last_id = self.next_call(completion, session_data, last_id)
            return self.screen, last_id
        except Exception as e:
            # 捕获API错误，特别是last_id失效时的400错误
            error_msg = str(e)
            # 检查HTTP状态码400或404，以及错误信息中的"not found"关键字
            if "400" in error_msg or "404" in error_msg or "not found" in error_msg.lower():
                # 如果是last_id失效错误，调用init_assistant方法重新初始化
                self.screen = []
                raw_screen, last_id = self.init_assistant(message, session_data, sys_prompt)
                for i in raw_screen.split('/'):
                    if len(i) > 10:
                        self.screen.append(i)
                return self.screen, last_id
            else:
                # 其他错误，重新抛出
                raise e
    
    def next_call(self,previous_message, session_data,last_id):
        cnt = 0
        current_last_id = last_id
        while True:
            function_call = next(
                (item for item in previous_message.output if item.type == "function_call"),None
            )
            if function_call is None:
                return previous_message.output[-1].content[0].text, current_last_id
            else:
                call_id = function_call.call_id
                call_arguments = function_call.arguments
                print(call_arguments)
                arg = json.loads(call_arguments)
                query = arg["query"]
                result = web_search(query,cnt)
                print('search query:',query)
                cnt += 1
                completion = client.responses.create(
                    model="doubao-seed-1-6-lite-251015",
                    previous_response_id = current_last_id,
                    input=[
                        {
                            'type':'function_call_output',
                            'call_id':call_id,
                            'output':json.dumps(result, ensure_ascii=False)
                        }
                    ],
                    caching={"type": "enabled"}, 
                    thinking={"type": "disabled"},
                    expire_at=int(time.time()) + CONTEXT_CACHE_TIME,
                )
                current_last_id = completion.id
                previous_message = completion
        return previous_message.output[-1].content[0].text, current_last_id


def connect_test(query):
    return f'这里是剧作家，收到请求：{query}'

def call_agent(query,add = None):
    print(f"这里是剧作家，你的需求语句为：{query}")
    print("请输入剧本名称：")
    name = input()
    script = Script(query,name,add)
    print("正在构思剧情...")
    script.get_abstract()
    print("正在生成大纲....")
    script.get_outline()
    print("大纲生成完毕，正在生成分镜...")
    for i in range(script.n):
        print(f"正在生成分镜 {i+1}...")
        script.get_screen(i)
        print(f"已生成分镜 {i+1}：\n{script.script[i]}")
        while 1:
            print("请输入修改建议：（无则输入无）")
            advice = input()
            if advice != "无":
                script.change_screen(advice,i)
            else:
                break
        print(f"修改后的分镜{i+1}：\n{script.script[i]}")
    p = script.save(script.name)
    print(f"已保存到{p}")
    return p

class ScreenwriterExecuter(AgentExecutor):
    def __init__(self):
        self.run = connect_test
    
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        actual_message = context.message.parts[0].root.text  # 实际的 Message 对象
        
        
        # 在事件循环中运行Decision_Agent
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            self.run,
            actual_message
        )
        
        # 从JSON格式转换回文本格式
        result_text = json.dumps(result, ensure_ascii=False)
        print(f"Decision Agent Result: {result_text},Type:{type(result_text)}")
        # 将结果封装到artifacts中返回
        await event_queue.enqueue_event(
            completed_task(
                context.task_id,
                context.context_id,
                [new_artifact(parts=[Part(root=TextPart(text=result_text))],name = 'test')],
                [context.message],
            )
        )
    
    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())



class Script:
    def __init__(self,query,name,add):
        self.query = query
        self.add = add
        self.name = name
        self.all_outline = ""
        self.abstract = ""
        self.outline = []
        self.all_stuff = None
        self.stuff = None
        self.n = None
        self.script = []
        self.data = {}

    def get_outline(self):
        self.all_outline = write_outline(self.abstract+self.add)
        self.outline = [i for i in self.all_outline.split('/')]
        self.n = len(self.outline)
        print(f"生成大纲，共{self.n}个分镜：")
        for i in range(self.n):
            print(f"{i+1}. {self.outline[i]}")
        change = 1
        while 1:
            print("请输入需要修改的大纲编号：（无则输入-1）")
            change = int(input())
            if change == -1:
                break
            self.change_outline(change)
            print(f"修改后的大纲：{self.outline[change-1]}")
            self.data["outline"] = self.outline
            self.data["all_outline"] = self.all_outline

    def get_abstract(self):
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": abstract_prompt+self.add},
                {"role": "user", "content": self.query},
            ],
            stream=False
        )
        self.abstract = response.choices[0].message.content
        print(f"剧情概括：{self.abstract}")
        while 1:
            print("是否需要修改？(y/n)")
            if_change = input()
            if if_change == 'y':
                print("请输入建议：")
                self.advice = input()
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": abstract_prompt+self.add},
                        {"role": "user", "content": self.query},
                    ],
                    stream=False
                )
                self.abstract = response.choices[0].message.content
                print(f"剧情概括：{self.abstract}")
            else:
                break
        
    
    def change_outline(self,num):
        print("修改建议：")
        advice = input()
        query = f"用户需求：{self.query}\n大纲：{self.outline[num-1]}\n修改建议：{advice}"
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": outline_prompt+self.add},
                {"role": "user", "content": query},
            ],
            stream=False
        )
        self.outline[num-1] = response.choices[0].message.content

    def get_screen(self,num):
        self.script.append(write_screen(self.query,self.outline[num]))
        
    def change_screen(self,advice,num):
        print("修改建议：")
        advice = input()
        query = f"用户需求：{self.query}\n大纲：{self.outline[num]}\n原分镜脚本：{self.script[num]}\n修改建议：{advice}"
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": screen_prompt+self.add},
                {"role": "user", "content": query},
            ],
            stream=False
        )
        self.script[num] = response.choices[0].message.content
    
    def save(self,filename):
        path = "./test/screen/"+filename+'.json'
        self.data = {
            "outline":self.outline,
            "all_outline":self.all_outline,
            "script":self.script,
            "abstract":self.abstract,
            "name":self.name,
            "n":self.n,
        }
        with open(path,'w',encoding = 'utf-8') as f:
            json.dump(self.data,f,ensure_ascii=False,indent=4)
        return path
        

def write_stuff(query,outline):
    query = '用户：'+query+'\n大纲：'+outline
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": stuff_prompt},
            {"role": "user", "content": query},
        ],
        stream=False
    )
    return response.choices[0].message.content

def write_screen(query,outline):
    query = '用户：' + query + '\n大纲：' + outline
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": screen_prompt},
            {"role": "user", "content": query},
        ],
        stream=False
    )
    return response.choices[0].message.content

def write_outline(query):
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": outline_prompt},
            {"role": "user", "content": query},
        ],
        stream=False
    )
    return response.choices[0].message.content

if __name__ == '__main__':
    story = Script(query = "卢浮宫《蒙娜丽莎》失窃",name = "monalisa")

