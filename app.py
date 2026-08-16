from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import os
import json
import socket
import traceback

app = Flask(__name__)
CORS(app)

# ==================== ⚙️ 网络代理与 AI 配置 ====================
USE_PROXY = False
PROXIES = {
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890"
}

# 严谨升级：使用绝对路径，防止因运行目录不同导致文件写入失败 (Error 500)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'approvals.json')

# ==================== 📂 网页路由 ====================
@app.route('/')
def index():
    return send_file('AI Agent.html')

@app.route('/approve_page')
def approve_page():
    return send_file('approve.html')

# ==================== ✍️ 局域网审批 API ====================
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                return {}
            return json.loads(content)
    except Exception as e:
        print(f"⚠️ 读取数据库报错: {e}")
        return {}

def save_db(data):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"⚠️ 写入数据库报错: {e}")
        traceback.print_exc()

# 报销人提交单据 (附带单据预览内容)
@app.route('/api/submit_approval', methods=['POST'])
def submit_approval():
    try:
        data = request.json or {}
        html_content = data.get('html_content', '<p style="text-align:center;color:#999;">无单据详情</p>')

        db = load_db()
        if 'current_form' not in db:
            db['current_form'] = {}
        
        db['current_form']['signatures'] = {} 
        db['current_form']['html_content'] = html_content
        save_db(db)
        
        print("✅ 收到前端推送，采购单审批快照已更新！")
        return jsonify({"status": "success"})
    except Exception as e:
        print("❌ 后台处理推送时发生错误：")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

# 领导获取待办列表与单据详情
@app.route('/api/pending_list', methods=['GET'])
def pending_list():
    return jsonify(load_db())

# 领导提交手写签名图片
@app.route('/api/sign', methods=['POST'])
def sign():
    try:
        data = request.json
        role = data.get('role') 
        sign_base64 = data.get('signature')

        db = load_db()
        if 'current_form' not in db:
            db['current_form'] = {'signatures': {}}
        if 'signatures' not in db['current_form']:
            db['current_form']['signatures'] = {}
            
        db['current_form']['signatures'][role] = sign_base64
        save_db(db)
        
        print(f"✅ 收到签字数据，角色：{role}")
        return jsonify({"status": "success"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

# ==================== 🤖 AI 识图 API ====================
@app.route('/api/ocr', methods=['POST'])
def ai_ocr():
    data = request.json
    api_key = data.get('api_key')
    mime_type = data.get('mime_type')
    base64_image = data.get('base64_image')
    prompt_text = data.get('prompt_text')

    if not all([api_key, mime_type, base64_image, prompt_text]):
        return jsonify({"error": "缺少必要参数"}), 400

    print("\n" + "="*50)
    print("🔍 收到网页发来的图片，正在连接 Google AI...")

    target_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
    payload = {
        "contents": [{"parts": [{"text": prompt_text}, {"inlineData": {"mimeType": mime_type, "data": base64_image}}]}],
        "generationConfig": {"temperature": 0.1}
    }
    headers = {"Content-Type": "application/json"}
    kwargs = {"json": payload, "headers": headers, "timeout": 60}
    if USE_PROXY: kwargs["proxies"] = PROXIES
        
    last_error = ""
    for model in target_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            response = requests.post(url, **kwargs)
            result = response.json()
            if response.status_code == 200 and "candidates" in result:
                ai_text = result["candidates"][0]["content"]["parts"][0]["text"]
                return jsonify({"result": ai_text, "model_used": model}), 200
            else:
                last_error = f"{model}: {result.get('error', {}).get('message', '未知错误')}"
        except Exception as e:
            last_error = str(e)

    return jsonify({"error": f"AI 模型匹配失败。\n最后报错: {last_error}"}), 400

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == '__main__':
    local_ip = get_ip()
    print("="*60)
    print("🚀 CCSA JV 局域网单据与审批系统已启动！")
    print(f"👉 本机直接访问地址: http://127.0.0.1:5000")
    print(f"👉 局域网访问地址: http://{local_ip}:5000")
    print(f"✍️ 请发给领导的签字链接: http://{local_ip}:5000/approve_page")
    print("="*60)
    app.run(host='0.0.0.0', port=5000, debug=False)