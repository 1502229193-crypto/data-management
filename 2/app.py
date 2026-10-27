from flask import Flask, request, jsonify, render_template_string
from pymongo import MongoClient
from bson.objectid import ObjectId
import datetime
import secrets

app = Flask(__name__)
app.secret_key = "survey_secret_key"

# 1. 数据库连接
client = MongoClient("mongodb://localhost:27017/")
db = client["survey_system"]

# 清空旧数据（保留干净的测试环境）
db.users.delete_many({})
db.questions.delete_many({})   # 【Phase 2 新增】独立题库集合
db.surveys.delete_many({})
db.submissions.delete_many({})

print("✅ Phase 2 数据库初始化完成（含独立题库与版本控制集合）！")

# -------------------------------------------------------------
# 路由 1: 首页
# -------------------------------------------------------------
@app.route('/')
def home():
    return render_template_string("""
    <h1>📝 基于 MongoDB 的在线问卷系统 (Phase 2 - 全局题库与版本控制)</h1>
    <p>状态：系统运行中 🚀</p>
    <hr>
    <h3>Phase 2 核心升级功能：</h3>
    <ul>
        <li><b>独立题库与复用</b>: <code>POST /api/questions/create</code></li>
        <li><b>题目版本升级</b>: <code>POST /api/questions/version/<q_id></code></li>
        <li><b>题目分享给他人</b>: <code>POST /api/questions/share</code></li>
        <li><b>引用追踪（查看题目被哪些问卷使用）</b>: <code>GET /api/questions/usages/<q_id></code></li>
        <li><b>创建问卷（引用题库题目及版本）</b>: <code>POST /api/surveys/create</code></li>
        <li><b>跨问卷题目全局统计</b>: <code>GET /api/questions/stats/<q_id></code></li>
    </ul>
    """)

# -------------------------------------------------------------
# 路由 2 & 3: 用户注册与登录
# -------------------------------------------------------------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    username, password = data.get('username'), data.get('password')
    if not username or not password:
        return jsonify({"status": "error", "message": "用户名和密码不能为空"}), 400
    if db.users.find_one({"username": username}):
        return jsonify({"status": "error", "message": "用户名已存在"}), 400
    db.users.insert_one({"username": username, "password": password, "created_at": datetime.datetime.now()})
    return jsonify({"status": "success", "message": "注册成功！"})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    user = db.users.find_one({"username": data.get('username'), "password": data.get('password')})
    if not user:
        return jsonify({"status": "error", "message": "用户名或密码错误"}), 401
    return jsonify({"status": "success", "message": "登录成功！", "username": data.get('username')})

# =============================================================
# Phase 2 核心新增：独立题库与版本控制管理 API
# =============================================================

# 1. 创建独立题目（存入全局 questions 集合）
@app.route('/api/questions/create', methods=['POST'])
def create_question():
    data = request.json or {}
    title = data.get('title')
    q_type = data.get('type') # single, multiple, text_blank, number_blank
    author = data.get('author')
    
    if not title or not q_type or not author:
        return jsonify({"status": "error", "message": "题目名称、类型和作者不能为空"}), 400
        
    question_doc = {
        "title": title,
        "type": q_type,
        "options": data.get('options', []),
        "required": data.get('required', True),
        "min_select": data.get('min_select'),
        "max_select": data.get('max_select'),
        "min_len": data.get('min_len'),
        "max_len": data.get('max_len'),
        "min_val": data.get('min_val'),
        "max_val": data.get('max_val'),
        "must_int": data.get('must_int'),
        "jump_logic": data.get('jump_logic', {}),
        
        # 版本与生命周期控制字段 (Phase 2)
        "version": 1,
        "parent_id": None,          # 首版父ID为None
        "is_locked": False,         # 是否被已发布问卷锁定
        
        # 权限与共享字段 (Phase 2)
        "owner": author,
        "shared_with": [],          # 共享给其他用户名列表
        "created_at": datetime.datetime.now()
    }
    
    result = db.questions.insert_one(question_doc)
    return jsonify({
        "status": "success", 
        "message": "题目创建成功！", 
        "question_id": str(result.inserted_id),
        "version": 1
    })

# 2. 题目分享给其他用户 (需求二)
@app.route('/api/questions/share', methods=['POST'])
def share_question():
    data = request.json or {}
    q_id = data.get('question_id')
    owner = data.get('owner')
    target_user = data.get('target_user')
    
    q = db.questions.find_one({"_id": ObjectId(q_id), "owner": owner})
    if not q:
        return jsonify({"status": "error", "message": "题目不存在或您无权操作"}), 404
        
    db.questions.update_one(
        {"_id": ObjectId(q_id)},
        {"$addToSet": {"shared_with": target_user}}
    )
    return jsonify({"status": "success", "message": f"题目已成功分享给 {target_user}"})

# 3. 基于现有题目创建新版本 (需求三、四、五)
@app.route('/api/questions/version/<q_id>', methods=['POST'])
def create_question_version(q_id):
    data = request.json or {}
    author = data.get('author')
    
    old_q = db.questions.find_one({"_id": ObjectId(q_id)})
    if not old_q:
        return jsonify({"status": "error", "message": "源题目不存在"}), 404
        
    # 检查权限：只有所有者或被分享者可以衍生新版本
    if old_q["owner"] != author and author not in old_q.get("shared_with", []):
        return jsonify({"status": "error", "message": "权限不足"}), 403
        
    # 构造新版本题目文档
    new_q_doc = {
        "title": data.get('title', old_q['title']),
        "type": old_q['type'],
        "options": data.get('options', old_q.get('options', [])),
        "required": data.get('required', old_q.get('required', True)),
        "min_select": data.get('min_select', old_q.get('min_select')),
        "max_select": data.get('max_select', old_q.get('max_select')),
        "min_len": data.get('min_len', old_q.get('min_len')),
        "max_len": data.get('max_len', old_q.get('max_len')),
        "min_val": data.get('min_val', old_q.get('min_val')),
        "max_val": data.get('max_val', old_q.get('max_val')),
        "must_int": data.get('must_int', old_q.get('must_int')),
        "jump_logic": data.get('jump_logic', old_q.get('jump_logic', {})),
        
        # 版本控制：继承版本链
        "version": old_q["version"] + 1,
        "parent_id": str(old_q["_id"]),
        "is_locked": False,
        "owner": author,
        "shared_with": old_q.get("shared_with", []),
        "created_at": datetime.datetime.now()
    }
    
    result = db.questions.insert_one(new_q_doc)
    return jsonify({
        "status": "success",
        "message": f"成功创建新版本 v{new_q_doc['version']}！",
        "new_question_id": str(result.inserted_id),
        "version": new_q_doc['version']
    })

# 4. 查看题目被哪些问卷使用（引用追踪 - 需求六）
@app.route('/api/questions/usages/<q_id>', methods=['GET'])
def get_question_usages(q_id):
    # 查找所有引用了该 question_id 的问卷
    surveys = list(db.surveys.find({"questions.question_id": q_id}, {"_id": 0, "survey_code": 1, "title": 1, "status": 1}))
    return jsonify({
        "status": "success",
        "question_id": q_id,
        "used_in_surveys": surveys,
        "usage_count": len(surveys)
    })

# -------------------------------------------------------------
# 路由 4 升级: 创建问卷 API (引用全局题库中的题目与版本)
# -------------------------------------------------------------
@app.route('/api/surveys/create', methods=['POST'])
def create_survey():
    data = request.json or {}
    title = data.get('title')
    description = data.get('description', '')
    author = data.get('author')
    question_refs = data.get('questions', []) # 格式：[{"question_id": "...", "version": 1, "sort_order": 1}, ...]
    
    if not title or not author or not question_refs:
        return jsonify({"status": "error", "message": "问卷标题、作者及题目引用列表不能为空"}), 400
        
    survey_code = secrets.token_hex(4)
    processed_questions = []
    
    for idx, ref in enumerate(question_refs):
        q_id = ref.get('question_id')
        ver = ref.get('version', 1)
        
        # 验证题目是否存在
        q_doc = db.questions.find_one({"_id": ObjectId(q_id), "version": ver})
        if not q_doc:
            return jsonify({"status": "error", "message": f"引用的题目 ID {q_id} (版本 v{ver}) 不存在"}), 400
            
        # 将该题目标记为锁定状态（已发布问卷引用，不可直接篡改原始内容 - 需求三）
        db.questions.update_one({"_id": ObjectId(q_id)}, {"$set": {"is_locked": True}})
        
        processed_questions.append({
            "question_id": q_id,
            "version": ver,
            "sort_order": ref.get('sort_order', idx + 1)
        })
    
    survey_doc = {
        "survey_code": survey_code,
        "survey_url": f"/survey/{survey_code}",
        "title": title,
        "description": description,
        "author": author,
        "status": "published",
        "questions": processed_questions, # 仅存引用关系与版本号
        "created_at": datetime.datetime.now()
    }
    
    db.surveys.insert_one(survey_doc)
    return jsonify({
        "status": "success", 
        "message": "问卷创建成功（已完成题库引用与版本锁定）！", 
        "survey_url": f"/survey/{survey_code}"
    })

# -------------------------------------------------------------
# 路由 5 & 6: 获取问卷列表与详情（组装完整题目内容返回）
# -------------------------------------------------------------
@app.route('/api/surveys/list/<username>', methods=['GET'])
def get_user_surveys(username):
    surveys = list(db.surveys.find({"author": username}, {"_id": 0}))
    return jsonify({"status": "success", "surveys": surveys})

@app.route('/api/survey/<survey_code>', methods=['GET'])
def get_survey_detail(survey_code):
    survey = db.surveys.find_one({"survey_code": survey_code}, {"_id": 0})
    if not survey:
        return jsonify({"status": "error", "message": "问卷不存在"}), 404
        
    # 动态组装：将引用的题目详细内容从 questions 集合中查出来组装在一起
    detailed_questions = []
    for ref in survey.get("questions", []):
        q_detail = db.questions.find_one({"_id": ObjectId(ref["question_id"]), "version": ref["version"]}, {"_id": 0})
        if q_detail:
            q_detail["question_id"] = ref["question_id"]
            q_detail["sort_order"] = ref["sort_order"]
            detailed_questions.append(q_detail)
            
    survey["questions"] = detailed_questions
    return jsonify({"status": "success", "survey": survey})

# -------------------------------------------------------------
# 路由 7: 计算下一题 (动态跳转引擎)
# -------------------------------------------------------------
@app.route('/api/survey/next_question', methods=['POST'])
def get_next_question():
    data = request.json or {}
    survey_code = data.get('survey_code')
    current_q_id = data.get('current_q_id') # 题目的 objectId 字符串
    user_answer = data.get('answer')
    
    survey = db.surveys.find_one({"survey_code": survey_code})
    if not survey:
        return jsonify({"status": "error", "message": "问卷不存在"}), 404
        
    # 获取完整题目内容
    questions = []
    for ref in survey.get("questions", []):
        q = db.questions.find_one({"_id": ObjectId(ref["question_id"]), "version": ref["version"]})
        if q:
            q["sort_order"] = ref["sort_order"]
            questions.append(q)
            
    questions.sort(key=lambda x: x["sort_order"])
    current_q = next((q for q in questions if str(q["_id"]) == current_q_id), None)
    
    if not current_q:
        return jsonify({"status": "error", "message": "当前题目不存在"}), 400
        
    jump_logic = current_q.get("jump_logic", {})
    next_q_id = None
    
    if current_q["type"] == "single" and str(user_answer) in jump_logic:
        next_q_id = jump_logic[str(user_answer)] # 目标sort_order或id
        
    if not next_q_id:
        all_orders = [q["sort_order"] for q in questions]
        current_idx = all_orders.index(current_q["sort_order"]) if current_q["sort_order"] in all_orders else -1
        if current_idx + 1 < len(all_orders):
            # 返回下一个顺序题的 objectId
            next_q_id = str(questions[current_idx + 1]["_id"])
        else:
            next_q_id = None

    return jsonify({"status": "success", "next_q_id": next_q_id})

# -------------------------------------------------------------
# 路由 8: 提交答卷与后端校验
# -------------------------------------------------------------
@app.route('/api/submissions/submit', methods=['POST'])
def submit_survey():
    data = request.json or {}
    survey_code = data.get('survey_code')
    answers = data.get('answers', {}) # {"<question_id>": answer}
    username = data.get('username', 'anonymous')
    
    survey = db.surveys.find_one({"survey_code": survey_code})
    if not survey:
        return jsonify({"status": "error", "message": "问卷不存在"}), 404
        
    # 验证并加载题目
    questions = []
    for ref in survey.get("questions", []):
        q = db.questions.find_one({"_id": ObjectId(ref["question_id"]), "version": ref["version"]})
        if q: questions.append(q)
        
    for q in questions:
        q_id_str = str(q["_id"])
        ans = answers.get(q_id_str)
        
        if q.get("required") and (ans is None or ans == "" or ans == []):
            return jsonify({"status": "error", "message": f"题目 [{q['title']}] 为必答题！"}), 400
            
        if ans is not None and ans != "":
            if q["type"] == "multiple":
                if not isinstance(ans, list): return jsonify({"status": "error", "message": "多选题答案格式错误"}), 400
                if "min_select" in q and len(ans) < q["min_select"]: return jsonify({"status": "error", "message": "少于最少选择项"}), 400
            elif q["type"] == "number_blank":
                try:
                    num_val = float(ans)
                    if q.get("must_int") and not num_val.is_integer(): return jsonify({"status": "error", "message": "必须为整数"}), 400
                except ValueError:
                    return jsonify({"status": "error", "message": "必须为有效数字"}), 400

    submission_doc = {
        "survey_code": survey_code,
        "username": username,
        "answers": answers,
        "submitted_at": datetime.datetime.now()
    }
    db.submissions.insert_one(submission_doc)
    return jsonify({"status": "success", "message": "答卷提交成功！"})

# -------------------------------------------------------------
# 路由 9 升级: 跨问卷题目全局统计分析（需求八）
# -------------------------------------------------------------
@app.route('/api/questions/stats/<q_id>', methods=['GET'])
def get_global_question_stats(q_id):
    """
    查看某一道题目（跨所有引用它的问卷）的总体回答分布情况
    """
    # 1. 找到所有包含该 question_id 的问卷
    surveys = list(db.surveys.find({"questions.question_id": q_id}))
    survey_codes = [s["survey_code"] for s in surveys]
    
    if not survey_codes:
        return jsonify({"status": "error", "message": "该题目未被任何问卷引用"}), 404
        
    # 2. 找到该题目的最新或指定定义
    q_doc = db.questions.find_one({"_id": ObjectId(q_id)})
    if not q_doc:
        return jsonify({"status": "error", "message": "题目不存在"}), 404
        
    # 3. 收集所有包含该 survey_code 的答卷中对该题的回答
    submissions = list(db.submissions.find({"survey_code": {"$in": survey_codes}}))
    
    answers_list = []
    for sub in submissions:
        ans = sub.get("answers", {}).get(q_id)
        if ans is not None and ans != "":
            answers_list.append(ans)
            
    # 4. 针对不同题型计算跨问卷聚合统计
    stat_data = {
        "question_id": q_id,
        "title": q_doc["title"],
        "type": q_doc["type"],
        "total_referenced_surveys": len(survey_codes),
        "total_global_answers": len(answers_list),
        "details": {}
    }
    
    q_type = q_doc["type"]
    if q_type == "single":
        counts = {opt: 0 for opt in q_doc.get("options", [])}
        for ans in answers_list:
            if ans in counts: counts[ans] += 1
        stat_data["details"] = counts
    elif q_type == "multiple":
        counts = {opt: 0 for opt in q_doc.get("options", [])}
        for ans in answers_list:
            if isinstance(ans, list):
                for item in ans:
                    if item in counts: counts[item] += 1
        stat_data["details"] = counts
    elif q_type == "number_blank":
        try:
            num_list = [float(ans) for ans in answers_list]
            stat_data["details"] = {
                "average": round(sum(num_list)/len(num_list), 2) if num_list else 0,
                "max": max(num_list) if num_list else 0,
                "min": min(num_list) if num_list else 0,
                "all_values": num_list
            }
        except ValueError:
            stat_data["details"] = {"error": "存在非法数据"}

    return jsonify({"status": "success", "global_statistics": stat_data})

# -------------------------------------------------------------
# 启动 Web 服务
# -------------------------------------------------------------
if __name__ == '__main__':
    print("🚀 正在启动 Phase 2 后端 Web 服务...")
    app.run(port=5000, debug=True)