from volcenginesdkarkruntime import Ark
import time

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

# 初始化Ark客户端
client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key='c96dbd1f-aeab-461c-90d6-8096b0baeecd',
)

class OutlineWriter:
    def __init__(self):
        self.last_id = None
        self.outline = []
    
    def init_assistant(self,message):
        # 创建初始对话，包含outline_writer的prompt和示例
        completion = client.responses.create(
            model="doubao-seed-1-6-251015",
            input=[
                {
                    'role':'system',
                    'content':f'你是一个专业的分镜大纲 writer，你的任务是根据用户的需求生成详细的分镜大纲。\n分镜大纲需要包含以下要素：\n1. 镜号：按顺序编号\n2. 详细画面：描述每个镜头的画面内容，包括景别、构图、动作、光线等\n3. 剧情概括：简要概括每个镜头的剧情内容\n\n分镜大纲的格式必须严格按照以下示例：\n{outline_example}。每部分的内容不需要太详细，后续会有专门生成分镜脚本的智能体。'
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
        return completion.output[-1].content[0].text
    
    def call(self,session_data:dict) -> str:
        """
        向火山方舟平台发送请求并返回内容
        :param message: 用户的需求
        :return: 分镜大纲
        """
        if not self.last_id:
            raw_outline = self.init_assistant(''.join(session_data['material']['idea']))
            for i in raw_outline.split('/'):
                if len(i) > 10:
                    self.outline.append(i)
            return self.outline
        completion = client.responses.create(
            model="doubao-seed-1-6-251015",
            previous_response_id = self.last_id,
            input=[
                {
                    'role':'system',
                    'content':f'你是一个专业的导演，现在请根据用户的修改请求，修改你之前写的大纲。\n大纲如下：\n{self.outline}'
                },
                {
                    'role':'user',
                    'content':str(session_data['modify_request']['outline'])
                }
            ],
            caching={"type": "enabled"}, 
            thinking={"type": "disabled"},
            expire_at=int(time.time()) + 360
        )
        self.last_id = completion.id
        raw_outline = completion.output[-1].content[0].text
        self.outline = []
        for i in raw_outline.split('/'):
            self.outline.append(i)
        return self.outline

if __name__ == "__main__":
    # 测试outline_writer功能
    writer = OutlineWriter()
    message = input("请输入您的需求：")
    while message != "exit":
        result = writer.call(message)
        print(f"Outline Writer Result: {result}")
        message = input("请输入您的需求：")