import os
import json
import requests
import uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

DATA_FILE = 'approvals.json'

# ==================== ⚙️ 本地数据存取 ====================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"current_form": None, "active_id": None}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"current_form": None, "active_id": None}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== 🌐 网页服务路由 ====================
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

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
    
    # 🌟 优化1：每次生成唯一的专属 ID
    doc_id = uuid.uuid4().hex[:10]
    
    data = {
        "active_id": doc_id,
        "current_form": {
            "html_content": html_content,
            "signatures": {
                "deputy": None,
                "manager": None
            }
        }
    }
    save_data(data)
    
    # 返回拼接好的唯一链接
    approval_url = f"{request.host_url.rstrip('/')}/approve_page?id={doc_id}"
    return jsonify({"status": "success", "approval_url": approval_url})

@app.route('/api/pending_list', methods=['GET'])
def pending_list():
    req_id = request.args.get('id')
    data = load_data()
    
    # 如果手机端带了 ID 来请求，校验链接是否已过期
    if req_id:
        if data.get("active_id") != req_id:
            return jsonify({"expired": True})
        return jsonify({"current_form": data.get("current_form")})
    
    # 电脑端刷新签名时，不需要校验ID，直接拉取最新表单
    return jsonify({"current_form": data.get("current_form")})

@app.route('/api/sign', methods=['POST'])
def sign():
    req = request.get_json() or {}
    role = req.get('role')
    sig_url = req.get('signature')
    sign_time = req.get('time', 'Unknown Time')
    sign_device = req.get('device', 'Unknown Device')
    doc_id = req.get('id')
    
    data = load_data()
    if not data.get("current_form"):
        return jsonify({"status": "error", "error": "当前没有审批单"}), 400
        
    # 校验签字提交时的链接是否仍然有效
    if doc_id and data.get("active_id") != doc_id:
        return jsonify({"status": "error", "error": "该链接已失效"}), 400
    
    if "signatures" not in data["current_form"]:
        data["current_form"]["signatures"] = {"deputy": None, "manager": None}
    
    # 🌟 优化3：同时保存签名图、签字时间、设备型号
    data["current_form"]["signatures"][role] = {
        "url": sig_url,
        "time": sign_time,
        "device": sign_device
    }
    
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

    target_models = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.0-pro"
    ]

    payload = {
        "contents": [{"parts": [{"text": prompt_text}, {"inlineData": {"mimeType": mime_type, "data": base64_image}}]}],
        "generationConfig": {"temperature": 0.1}
    }
    
    headers = {"Content-Type": "application/json"}
    kwargs = {"json": payload, "headers": headers, "timeout": 20}
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
                last_error = result.get("error", {}).get("message", "接口未返回正确结果")
        except requests.exceptions.Timeout:
            last_error = f"{model} 请求超时"
        except Exception as e:
            last_error = str(e)

    return jsonify({"error": f"AI 模型匹配失败。\n最后报错: {last_error}"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)