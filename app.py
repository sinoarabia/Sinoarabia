import os
import json
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

DATA_FILE = 'approvals.json'

# ==================== ⚙️ 本地数据存取 (审批流使用) ====================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"current_form": None}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"current_form": None}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== 🌐 网页服务路由 ====================
@app.route('/')
def index():
    return send_from_directory('.', 'AI Agent.html')

@app.route('/approve_page')
def approve_page():
    return send_from_directory('.', 'approve.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# ==================== ✍️ 在线审批流接口 ====================
@app.route('/api/submit_approval', methods=['POST'])
def submit_approval():
    req = request.get_json() or {}
    html_content = req.get('html_content', '')
    data = {
        "current_form": {
            "html_content": html_content,
            "signatures": {
                "deputy": None,
                "manager": None
            }
        }
    }
    save_data(data)
    return jsonify({"status": "success"})

@app.route('/api/pending_list', methods=['GET'])
def pending_list():
    data = load_data()
    return jsonify(data)

@app.route('/api/sign', methods=['POST'])
def sign():
    req = request.get_json() or {}
    role = req.get('role')
    sig_url = req.get('signature')
    
    data = load_data()
    if not data.get("current_form"):
        return jsonify({"status": "error", "error": "No active approval"}), 400
    
    if "signatures" not in data["current_form"]:
        data["current_form"]["signatures"] = {"deputy": None, "manager": None}
    
    data["current_form"]["signatures"][role] = sig_url
    save_data(data)
    return jsonify({"status": "success"})

# ==================== 🤖 AI 发票智能识别接口 ====================
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

    # 模型池：向下兼容，确保识别绝对可用
    target_models = [
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]

    # 修复了 Google API 严格要求的下划线参数命名规范
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt_text},
                {"inline_data": {"mime_type": mime_type, "data": base64_image}}
            ]
        }],
        "generationConfig": {"temperature": 0.1}
    }
    
    headers = {"Content-Type": "application/json"}
    kwargs = {
        "json": payload,
        "headers": headers,
        "timeout": 60 
    }
    
    last_error = ""

    for model in target_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        print(f"▶️ 正在调用 AI 识图模型: {model} ...")
        
        try:
            response = requests.post(url, **kwargs)
            result = response.json()
            
            if response.status_code == 200 and "candidates" in result:
                ai_text = result["candidates"][0]["content"]["parts"][0]["text"]
                print(f"🎉 识别成功！所用模型: {model}")
                return jsonify({"result": ai_text, "model_used": model}), 200
            else:
                err_msg = result.get("error", {}).get("message", "接口未返回正确结果")
                print(f"❌ {model} 响应异常: {err_msg}")
                last_error = f"{model}: {err_msg}"
                
        except requests.exceptions.Timeout:
            last_error = f"{model} 请求超时 (60秒)"
            print(f"⚠️ {last_error}")
        except Exception as e:
            last_error = str(e)
            print(f"❌ 连接失败: {last_error}")

    return jsonify({"error": f"AI 模型匹配失败。\n最后报错: {last_error}"}), 400


if __name__ == '__main__':
    print("="*50)
    print("🚀 CCSA JV 终极版后台已启动！")
    print("✅ 已包含：在线审批流引擎 + AI 智能识票引擎")
    print("="*50)
    # Render 部署必备：监听 0.0.0.0 才能外网访问
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)