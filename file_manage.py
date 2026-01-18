import os
import json

class UserFile:
    def __init__(self,user):
        ##这里需要添加保存会话记录到用户文件夹下，以及还需要一个用户加载会话记录的函数
        self.user = user
        self.file_path = f'./user_files/{user}'
        self.project_path = f'./user_files/{user}/projects/'
        if not os.path.exists(self.file_path):
            os.makedirs(self.file_path)
        # 创建项目文件夹，如果它不存在
        if not os.path.exists(self.project_path):
            os.makedirs(self.project_path)
        self.user_project = [i for i in os.listdir(self.project_path) if os.path.isdir(os.path.join(self.project_path,i))]
        self.project_content = {}
        for i in self.user_project:
            self.project_content[i] = self.load_content(i)
        self.session_path = os.path.join(self.file_path,'session_history.json')
        if not os.path.exists(self.session_path):
            with open(self.session_path,'w',encoding = 'utf-8') as file:
                json.dump({}, file, ensure_ascii=False, indent=4)

    def init_project(self,project_name):
        i = 1
        new_project_name = project_name
        while new_project_name in self.user_project:
            new_project_name = f"{project_name}_{i}"
            i += 1
        self.user_project.append(new_project_name)
        self.project_content[new_project_name] = None
        os.makedirs(os.path.join(self.project_path,new_project_name))
        content = {
            'material':None,
            'session_id':None
        }
        self.project_content[new_project_name] = content
        with open(os.path.join(self.project_path,new_project_name, 'project.json'), 'w', encoding='utf-8') as file:
            json.dump(content, file, ensure_ascii=False, indent=4)
        return new_project_name
    
    def load_content(self,project_name):
        if project_name not in self.user_project:
            raise FileNotFoundError(f"项目 {project_name} 不存在")
        with open(os.path.join(self.project_path,project_name, 'project.json'), 'r', encoding='utf-8') as file:
            self.project_content[project_name] = json.load(file)
        return self.project_content[project_name]
    
    def save_content(self,project_name,material,session_id):
        if project_name not in self.user_project:
            os.makedirs(os.path.join(self.project_path,project_name))
            self.user_project.append(project_name)
        self.project_content[project_name]['material'] = material
        self.project_content[project_name]['session_id'] = session_id
        with open(os.path.join(self.project_path,project_name, 'project.json'), 'w', encoding='utf-8') as file:
            json.dump(self.project_content[project_name], file, ensure_ascii=False, indent=4)
    
    def save_session(self,session_id,session_data):
        now_session = self.load_session()
        now_session[session_id] = session_data
        with open(self.session_path,'w',encoding = 'utf-8') as file:
            json.dump(now_session,file,ensure_ascii=False, indent=4)

    def load_session(self):
        with open(self.session_path,'r',encoding = 'utf-8') as file:
            now_session = json.load(file)
            return now_session