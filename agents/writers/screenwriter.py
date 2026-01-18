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



client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key='c96dbd1f-aeab-461c-90d6-8096b0baeecd',
)


change_outline_prompt = '''
你是一个编剧，请根据用户提供的大纲建议，在大纲基础上进行修改，确保大纲内容与用户需求相符。
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
你是一个编剧，请根据用户提供的修改建议，在分镜基础上进行修改，确保分镜内容与用户需求和大纲相符。
'''

script_example = '''
镜号 1
场景：米勒星球的浅海区域，海面呈深蓝灰色且平静无波，泛着微弱反光，远处海平面矗立着形似 “山峦” 的巨大轮廓，背景悬着黑洞，投射出淡紫色引力光晕；徘徊者号飞船平稳着陆浅海，船体下半部分浸在水中，布兰德、道尔在不远处的米勒飞船残骸（半浸水中，金属外壳锈蚀、零件散落）旁探寻，库珀留守驾驶舱内观察。
【风格】科幻写实风格，冷色调为主（深蓝灰海面、银灰航天服、暗紫黑洞光晕），高对比度，光影层次分明（黑洞光晕照亮海面局部，残骸投射深色阴影，驾驶舱内仪器蓝光形成局部亮面）
角色：库珀：典型的中年男性形象，发型是利落的短黑发，看起来干练，身形偏精瘦硬朗，常穿浅灰 T 恤，面部线条清晰，气质兼具 “父亲的温和” 与 “宇航员的坚毅”。
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
用户正在用视频生成模型创作AI视频，你的任务是根据用户传入的分镜大纲创作一些用于视频生成的分镜脚本。分镜大纲分好了每一个镜号，每一个镜号要创作一个分镜脚本。
如果用户传入的大纲中存在你不了解的信息，你需要先使用联网搜索工具确认信息（如角色外形描述等），然后再创作分镜脚本。
每个分镜脚本控制大约5秒的镜头。
每个分镜脚本写完后用’/‘隔开
单个分镜脚本举例：{script_example}；
'''

abstract_prompt = f'''
你是一个编剧，你的任务是根据用户的需求创作一个剧情概括，要求简洁明了，重点突出剧情走向。
由于可生成视频的长度很短，概括的内容应集中在某一个事件上。
概括举例：{abstract_example}
'''

outline_prompt = f'''
你是一个编剧，你的任务是根据用户的需求创作一个分镜大纲。由于可生成视频的长度很短，大纲的所有分镜应集中描绘一个事件。
大纲以分镜为载体，写出每个分镜的场景、画面和简要剧情，要求突出场景和画面，涉及到的人物不要超过三个
编写大纲中涉及到的人物尽量用影视作品中与他相似的角色代替，如出现“男性，老魔法师”的形象可以用甘道夫或邓布利多代替，这是为了方便后续的分镜创作智能体创作角色。
大纲示例：{outline_example}；
!!注意!!每个分镜写完后用{'/'}隔开
'''

class ScreenWriter:
    def __init__(self):
        self.last_id = None
        self.screen = []
    
    def init_assistant(self,message):
        # 创建初始对话，包含outline_writer的prompt和示例
        completion = client.responses.create(
            model="doubao-seed-1-6-251015",
            tools = tools,
            input=[
                {
                    'role':'system',
                    'content':screen_prompt
                },
                {
                    'role':'user',
                    'content':message
                }
            ],
            caching={"type": "enabled"}, 
            thinking={"type": "disabled"},
            expire_at=int(time.time()) + 360
        )
        self.last_id = completion.id
        return self.next_call(completion)
    
    def call(self,session_data:dict) -> str:
        """
        向火山方舟平台发送请求并返回内容
        :param message: 用户的需求
        :return: 分镜大纲
        """
        if not self.last_id:
            raw_screen = self.init_assistant(''.join(session_data['material']['idea']))
            for i in raw_screen.split('/'):
                if len(i) > 10:
                    self.screen.append(i)
            return self.screen
        need_modify = session_data['material']['screen'][session_data['modify_num']-1]
        completion = client.responses.create(
            model="doubao-seed-1-6-251015",
            previous_response_id = self.last_id,
            input=[
                {
                    'role':'system',
                    'content':f'请根据用户的修改请求，修改这个分镜脚本{need_modify}。这次脚本中不需要加其他特殊符号'
                },
                {
                    'role':'user',
                    'content':session_data['modify_request']['screen']
                }
            ],
            caching={"type": "enabled"}, 
            thinking={"type": "disabled"},
            expire_at=int(time.time()) + 360
        )
        self.last_id = completion.id
        self.screen[session_data['modify_num']-1] = self.next_call(completion)
        return self.screen
    
    def next_call(self,previous_message):
        while True:
            function_call = next(
                (item for item in previous_message.output if item.type == "function_call"),None
            )
            if function_call is None:
                return previous_message.output[-1].content[0].text
            else:
                call_id = function_call.call_id
                call_arguments = function_call.arguments
                arg = json.loads(call_arguments)
                query = arg["query"]
                result = web_search(query)
                print('search query:',query)
                completion = client.responses.create(
                    model="doubao-seed-1-6-251015",
                    previous_response_id = self.last_id,
                    input=[
                        {
                            'type':'function_call_output',
                            'call_id':call_id,
                            'output':json.dumps(result, ensure_ascii=False)
                        }
                    ],
                    caching={"type": "enabled"}, 
                    thinking={"type": "disabled"},
                    expire_at=int(time.time()) + 360
                )
                self.last_id = completion.id
                previous_message = completion
        return previous_message.output[-1].content[0].text


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

