from flask import Flask, request, jsonify, render_template_string
from pymongo import MongoClient
from bson.objectid import ObjectId
import datetime
import secrets

app = Flask(__name__)
# 密钥，用于 session/安全（可设任意字符串）
app.secret_key = "survey_secret_key"

# 1. 数据库连接
client = MongoClient("mongodb://localhost:27017/")
db = client["survey_system"]

# 清空旧数据（每次重新运行保留干净环境）
db.users.delete_many({})
db.surveys.delete_many({})
db.submissions.delete_many({})

print("✅ 数据库初始化完成！")

# -------------------------------------------------------------
# 路由 1: 首页（简单 HTML 界面）
# -------------------------------------------------------------
@app.route('/')
def home():
    html = """
    <h1>📝 基于 MongoDB 的在线问卷系统</h1>
    <p>状态：系统运行中 🚀</p>
    <hr>
    <h3>1. 测试快速创建问卷 (API 表单)</h3>
    <form action="/api/surveys/create" method="POST" onsubmit="alert('请通过代码或工具发送 JSON 请求，或者我们用下方脚本测试！'); return false;">
        <p>标题: <input type="text" name="title" value="同学满意度调查"></p>
        <p>作者: <input type="text" name="author" value="zhangsan"></p>
        <button type="submit">创建问卷</button>
    </form>
    <hr>
    <h3>可用 API 列表：</h3>
    <ul>
        <li><b>注册</b>: <code>POST /api/register</code></li>
        <li><b>登录</b>: <code>POST /api/login</code></li>
        <li><b>创建问卷</b>: <code>POST /api/surveys/create</code></li>
        <li><b>查看某用户的问卷</b>: <code>GET /api/surveys/list/&lt;username&gt;</code></li>
    </ul>
    """
    return render_template_string(html)

# -------------------------------------------------------------
# 路由 2: 用户注册 API
# -------------------------------------------------------------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"status": "error", "message": "用户名和密码不能为空"}), 400
        
    if db.users.find_one({"username": username}):
        return jsonify({"status": "error", "message": "用户名已存在"}), 400
        
    user_doc = {
        "username": username,
        "password": password,
        "created_at": datetime.datetime.now()
    }
    db.users.insert_one(user_doc)
    return jsonify({"status": "success", "message": "注册成功！"})

# -------------------------------------------------------------
# 路由 3: 用户登录 API
# -------------------------------------------------------------
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    
    user = db.users.find_one({"username": username, "password": password})
    if not user:
        return jsonify({"status": "error", "message": "用户名或密码错误"}), 401
        
    return jsonify({"status": "success", "message": "登录成功！", "username": username})

# -------------------------------------------------------------
# 路由 4: 创建问卷 API (符合 MongoDB 嵌套 Schema 设计)
# -------------------------------------------------------------
@app.route('/api/surveys/create', methods=['POST'])
def create_survey():
    data = request.json or {}
    
    # 基础信息
    title = data.get('title')
    description = data.get('description', '')
    author = data.get('author') # 创建者用户名
    
    if not title or not author:
        return jsonify({"status": "error", "message": "问卷标题和作者不能为空"}), 400
        
    # 生成唯一的问卷短 ID，用于构造访问链接 /survey/xxxxxx
    survey_code = secrets.token_hex(4) # 生成类似 'a1b2c3d4' 的8位随机串
    
    # 题目列表（包含单选、多选、填空，以及跳转和校验规则）
    # 示例结构：
    questions = data.get('questions', [
        {
            "q_id": 1,
            "type": "single", # 单选
            "title": "你的性别",
            "options": ["男", "女", "其他"],
            "required": True,
            "jump_logic": {"男": 5, "女": 3} # 示例跳转逻辑：选男跳到第5题，选女跳到第3题
        },
        {
            "q_id": 2,
            "type": "number_blank", # 数字填空
            "title": "你的年龄",
            "min_val": 0,
            "max_val": 120,
            "must_int": True,
            "required": True
        }
    ])
    
    survey_doc = {
        "survey_code": survey_code,
        "survey_url": f"/survey/{survey_code}",
        "title": title,
        "description": description,
        "author": author,
        "status": "published", # published 已发布, closed 已关闭
        "questions": questions,
        "created_at": datetime.datetime.now()
    }
    
    db.surveys.insert_one(survey_doc)
    return jsonify({
        "status": "success", 
        "message": "问卷创建成功！", 
        "survey_url": f"/survey/{survey_code}"
    })

# -------------------------------------------------------------
# 路由 5: 获取某个用户创建的问卷列表
# -------------------------------------------------------------
@app.route('/api/surveys/list/<username>', methods=['GET'])
def get_user_surveys(username):
    # 每个用户只能看到自己创建的问卷
    surveys = list(db.surveys.find({"author": username}, {"_id": 0}))
    return jsonify({"status": "success", "surveys": surveys})

# -------------------------------------------------------------
# 路由 6: 获取指定问卷详情（提供给填写界面）
# -------------------------------------------------------------
@app.route('/api/survey/<survey_code>', methods=['GET'])
def get_survey_detail(survey_code):
    survey = db.surveys.find_one({"survey_code": survey_code}, {"_id": 0})
    if not survey:
        return jsonify({"status": "error", "message": "问卷不存在"}), 404
    if survey.get("status") == "closed":
        return jsonify({"status": "error", "message": "该问卷已关闭"}), 400
    return jsonify({"status": "success", "survey": survey})

# -------------------------------------------------------------
# 路由 7: 计算下一题 (动态跳转引擎)
# -------------------------------------------------------------
@app.route('/api/survey/next_question', methods=['POST'])
def get_next_question():
    """
    根据当前题目 ID 和用户的选项/回答，计算下一题的 ID
    """
    data = request.json or {}
    survey_code = data.get('survey_code')
    current_q_id = data.get('current_q_id')
    user_answer = data.get('answer') # 用户当前的回答
    
    survey = db.surveys.find_one({"survey_code": survey_code})
    if not survey:
        return jsonify({"status": "error", "message": "问卷不存在"}), 404
        
    questions = survey.get("questions", [])
    # 查找当前题目
    current_q = next((q for q in questions if q["q_id"] == current_q_id), None)
    
    if not current_q:
        return jsonify({"status": "error", "message": "当前题目不存在"}), 400
        
    # 检查是否有显式设置的跳转逻辑 (jump_logic)
    jump_logic = current_q.get("jump_logic", {})
    next_q_id = None
    
    # 1. 单选跳转规则校验 (例如: {"男": 5, "女": 3})
    if current_q["type"] == "single" and str(user_answer) in jump_logic:
        next_q_id = jump_logic[str(user_answer)]
        
    # 2. 数字填空跳转规则校验 (例如: {"<18": 3, ">=18": 5})
    elif current_q["type"] == "number_blank" and isinstance(jump_logic, dict):
        try:
            val = float(user_answer)
            for rule_str, target_id in jump_logic.items():
                if rule_str.startswith("<=") and val <= float(rule_str[2:]):
                    next_q_id = target_id; break
                elif rule_str.startswith(">=") and val >= float(rule_str[2:]):
                    next_q_id = target_id; break
                elif rule_str.startswith("<") and val < float(rule_str[1:]):
                    next_q_id = target_id; break
                elif rule_str.startswith(">") and val > float(rule_str[1:]):
                    next_q_id = target_id; break
                elif rule_str.startswith("==") and val == float(rule_str[2:]):
                    next_q_id = target_id; break
        except (ValueError, TypeError):
            pass

    # 如果没有触发特殊的跳转逻辑，则默认进入按顺序的下一题
    if not next_q_id:
        all_ids = [q["q_id"] for q in questions]
        current_idx = all_ids.index(current_q_id) if current_q_id in all_ids else -1
        if current_idx + 1 < len(all_ids):
            next_q_id = all_ids[current_idx + 1]
        else:
            next_q_id = None # 表示已答完最后一题，准备提交

    return jsonify({"status": "success", "next_q_id": next_q_id})

# -------------------------------------------------------------
# 路由 8: 提交答卷与后端数据校验
# -------------------------------------------------------------
@app.route('/api/submissions/submit', methods=['POST'])
def submit_survey():
    data = request.json or {}
    survey_code = data.get('survey_code')
    answers = data.get('answers', {}) # 字典格式：{"1": "男", "2": 25}
    username = data.get('username', 'anonymous') # 允许指定用户或匿名
    
    survey = db.surveys.find_one({"survey_code": survey_code})
    if not survey:
        return jsonify({"status": "error", "message": "问卷不存在"}), 404
        
    questions = survey.get("questions", [])
    
    # 后端严格校验数据合法性
    for q in questions:
        q_id_str = str(q["q_id"])
        ans = answers.get(q_id_str)
        
        # 1. 必答校验
        if q.get("required") and (ans is None or ans == "" or ans == []):
            return jsonify({"status": "error", "message": f"第 {q['q_id']} 题 [{q['title']}] 为必答题！"}), 400
            
        if ans is not None and ans != "":
            # 2. 多选题选择数量校验
            if q["type"] == "multiple":
                if not isinstance(ans, list):
                    return jsonify({"status": "error", "message": f"第 {q['q_id']} 题答案格式错误"}), 400
                if "min_select" in q and len(ans) < q["min_select"]:
                    return jsonify({"status": "error", "message": f"第 {q['q_id']} 题至少需要选择 {q['min_select']} 项"}), 400
                if "max_select" in q and len(ans) > q["max_select"]:
                    return jsonify({"status": "error", "message": f"第 {q['q_id']} 题最多只能选择 {q['max_select']} 项"}), 400
                    
            # 3. 文本填空字数校验
            elif q["type"] == "text_blank":
                ans_str = str(ans)
                if "min_len" in q and len(ans_str) < q["min_len"]:
                    return jsonify({"status": "error", "message": f"第 {q['q_id']} 题最少需要输入 {q['min_len']} 个字"}), 400
                if "max_len" in q and len(ans_str) > q["max_len"]:
                    return jsonify({"status": "error", "message": f"第 {q['q_id']} 题最多允许输入 {q['max_len']} 个字"}), 400
                    
            # 4. 数字填空数值与整数校验
            elif q["type"] == "number_blank":
                try:
                    num_val = float(ans)
                    if q.get("must_int") and not num_val.is_integer():
                        return jsonify({"status": "error", "message": f"第 {q['q_id']} 题必须填入整数"}), 400
                    if "min_val" in q and num_val < q["min_val"]:
                        return jsonify({"status": "error", "message": f"第 {q['q_id']} 题数值不能小于 {q['min_val']}"}), 400
                    if "max_val" in q and num_val > q["max_val"]:
                        return jsonify({"status": "error", "message": f"第 {q['q_id']} 题数值不能大于 {q['max_val']}"}), 400
                except ValueError:
                    return jsonify({"status": "error", "message": f"第 {q['q_id']} 题必须填入有效数字"}), 400

    # 校验全部通过，保存答卷到 submissions 集合
    submission_doc = {
        "survey_code": survey_code,
        "username": username,
        "answers": answers,
        "submitted_at": datetime.datetime.now()
    }
    db.submissions.insert_one(submission_doc)
    return jsonify({"status": "success", "message": "问卷提交成功！"})

# -------------------------------------------------------------
# 路由 9: 查看问卷统计结果 (使用 MongoDB 聚合与数据分析)
# -------------------------------------------------------------
@app.route('/api/survey/stats/<survey_code>', methods=['GET'])
def get_survey_stats(survey_code):
    survey = db.surveys.find_one({"survey_code": survey_code}, {"_id": 0})
    if not survey:
        return jsonify({"status": "error", "message": "问卷不存在"}), 404
        
    questions = survey.get("questions", [])
    
    # 获取该问卷的所有答卷
    submissions = list(db.submissions.find({"survey_code": survey_code}))
    total_submissions = len(submissions)
    
    question_stats = {}
    
    for q in questions:
        q_id_str = str(q["q_id"])
        q_type = q["type"]
        q_title = q["title"]
        
        # 初始化统计结构
        stat_data = {
            "title": q_title,
            "type": q_type,
            "answer_count": 0,
            "details": {}
        }
        
        # 收集当前题目的所有回答
        answers_list = []
        for sub in submissions:
            ans = sub.get("answers", {}).get(q_id_str)
            if ans is not None and ans != "":
                answers_list.append(ans)
                
        stat_data["answer_count"] = len(answers_list)
        
        # 1. 单选题统计：计算每个选项的频次
        if q_type == "single":
            counts = {opt: 0 for opt in q.get("options", [])}
            for ans in answers_list:
                if ans in counts:
                    counts[ans] += 1
            stat_data["details"] = counts
            
        # 2. 多选题统计：计算各个选项被选择的总次数
        elif q_type == "multiple":
            counts = {opt: 0 for opt in q.get("options", [])}
            for ans in answers_list:
                if isinstance(ans, list):
                    for item in ans:
                        if item in counts:
                            counts[item] += 1
            stat_data["details"] = counts
            
        # 3. 文本填空统计：返回所有文本列表
        elif q_type == "text_blank":
            stat_data["details"] = {"texts": answers_list}
            
        # 4. 数字填空统计：计算数字平均值和最大最小值
        elif q_type == "number_blank":
            try:
                num_list = [float(ans) for ans in answers_list]
                if num_list:
                    avg_val = sum(num_list) / len(num_list)
                    max_val = max(num_list)
                    min_val = min(num_list)
                else:
                    avg_val, max_val, min_val = 0, 0, 0
                stat_data["details"] = {
                    "average": round(avg_val, 2),
                    "max": max_val,
                    "min": min_val,
                    "all_values": num_list
                }
            except ValueError:
                stat_data["details"] = {"error": "存在非数字的非法数据"}
                
        question_stats[q_id_str] = stat_data

    return jsonify({
        "status": "success",
        "survey_title": survey["title"],
        "total_submissions": total_submissions,
        "statistics": question_stats
    })

# -------------------------------------------------------------
# 启动 Web 服务
# -------------------------------------------------------------
if __name__ == '__main__':
    print("🚀 正在启动后端 Web 服务...")
    app.run(port=5000, debug=True)

