from flask import Flask, request, jsonify
import os
import sys
from agents.hello_world.hello_world_agent import hello_world_agent
# 导入你的自定义Python代码（根据实际文件名修改）


app = Flask(__name__)

# 配置：证书存储目录（自动创建）
CERT_UPLOAD_FOLDER = 'certs'
if not os.path.exists(CERT_UPLOAD_FOLDER):
    os.makedirs(CERT_UPLOAD_FOLDER)

# 允许上传的证书文件格式（可根据需求扩展）
ALLOWED_EXTENSIONS = {'pem', 'cer', 'crt', 'key', 'pfx'}

# 验证文件格式
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 核心接口：接收证书上传并运行自定义代码
@app.route('/upload-cert', methods=['POST'])
def upload_cert():
    try:
        # 1. 检查是否有文件上传
        if 'cert_file' not in request.files:
            return jsonify({"status": "error", "message": "未上传证书文件"}), 400

        file = request.files['cert_file']

        # 4. 保存文件到服务器
        file_path = os.path.join(CERT_UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        app.logger.info(f"证书文件已保存：{file_path}")

        # 5. 调用你的自定义Python代码处理证书（核心步骤）
        # 这里根据你的需求修改：例如解析证书、验证有效性、执行业务逻辑等
      # 自定义函数，需在your_code.py中实现

        # 6. 返回处理结果给外部设备
        return jsonify({
            "status": "success",
            "message": "证书上传并处理成功",
            "file_path": file_path,
        }), 200

    except Exception as e:
        app.logger.error(f"处理失败：{str(e)}")
        return jsonify({"status": "error", "message": f"处理失败：{str(e)}"}), 500

# 健康检查接口（可选，用于测试服务是否正常运行）
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "running", "message": "服务正常"}), 200

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "status": "success",
        "message": "证书上传服务已启动",
        "available_apis": [
            {
                "path": "/upload-cert",
                "method": "POST",
                "description": "上传证书文件",
                "params": {"cert_file": "证书文件（支持.pem/.cer/.crt等）"}
            },
            {
                "path": "/health",
                "method": "GET",
                "description": "服务健康检查"
            }
        ]
    }), 200

# 2. 处理 favicon.ico 请求，返回空响应（避免404）
@app.route('/favicon.ico', methods=['GET'])
def favicon():
    return '', 204  # 204 表示无内容，不返回任何数据

@app.route('/list-certs', methods=['GET'])
def list_certs():
    try:
        # 检查certs文件夹是否存在
        if not os.path.exists(CERT_UPLOAD_FOLDER):
            return jsonify({
                "status": "success",
                "message": "证书文件夹为空",
                "file_count": 0,
                "files": []
            }), 200

        # 遍历文件夹，获取文件详情
        file_list = []
        for filename in os.listdir(CERT_UPLOAD_FOLDER):
            # 排除文件夹（只显示文件）
            file_path = os.path.join(CERT_UPLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                # 获取文件大小（单位：KB）
                file_size = round(os.path.getsize(file_path) / 1024, 2)
                # 获取文件最后修改时间（格式化）
                modify_time = time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(os.path.getmtime(file_path))
                )
                # 添加文件信息到列表
                file_list.append({
                    "filename": filename,
                    "size_kb": file_size,
                    "modify_time": modify_time,
                    "file_path": file_path
                })

        # 按修改时间倒序排序（最新的文件在前面）
        file_list.sort(key=lambda x: x["modify_time"], reverse=True)

        return jsonify({
            "status": "success",
            "message": f"found {len(file_list)} certificates",
            "file_count": len(file_list),
            "files": file_list
        }), 200

    except Exception as e:
        app.logger.error(f"列出文件失败：{str(e)}")
        return jsonify({
            "status": "error",
            "message": f"列出文件失败：{str(e)}"
        }), 500

# 新增：无参数触发智能体（直接访问链接就运行）
@app.route('/hello', methods=['GET'])
def hello_world_agent():
    try:
        app.logger.info("开始运行智能体...")
        
        # 调用你的智能体核心逻辑（替换为你实际的智能体函数）
        # 示例：让智能体处理 certs 文件夹中最新的证书
        agent_result = hello_world_agent()  # 需在 your_code.py 中实现
        
        app.logger.info("智能体运行完成")
        return jsonify({
            "status": "success",
            "message": "智能体运行成功",
            "agent_result": agent_result
        }), 200

    except Exception as e:
        app.logger.error(f"智能体运行失败：{str(e)}")
        return jsonify({
            "status": "error",
            "message": f"智能体运行失败：{str(e)}"
        }), 500

if __name__ == '__main__':
    # 关键配置：0.0.0.0 允许外部设备访问，port=5000（可修改）
    # debug=True 仅开发环境使用，生产环境请改为False
    app.run(host='0.0.0.0', port=5000, debug=False)