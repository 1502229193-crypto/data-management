import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_pipeline():
    print("================ 1. 测试用户注册与登录 ================")
    reg_res = requests.post(f"{BASE_URL}/api/register", json={"username": "test_user", "password": "password123"}).json()
    print("注册结果:", reg_res)
    
    login_res = requests.post(f"{BASE_URL}/api/login", json={"username": "test_user", "password": "password123"}).json()
    print("登录结果:", login_res)

    print("\n================ 2. 测试创建问卷（含单选、多选、数字填空及跳转） ================")
    survey_payload = {
        "title": "大学生生活习惯调查",
        "description": "测试问卷跳转与校验逻辑",
        "author": "test_user",
        "questions": [
            {
                "q_id": 1,
                "type": "single",
                "title": "你的年级是？",
                "options": ["大一", "大二", "大三", "大四"],
                "required": True,
                "jump_logic": {"大一": 3}  # 大一直接跳到第3题
            },
            {
                "q_id": 2,
                "type": "multiple",
                "title": "你常用的学习软件（至少选2个，最多3个）",
                "options": ["Notion", "VSCode", "Anki", "GoodNotes"],
                "min_select": 2,
                "max_select": 3,
                "required": True
            },
            {
                "q_id": 3,
                "type": "number_blank",
                "title": "你每天学习的时长（小时，0-24之间整数）",
                "min_val": 0,
                "max_val": 24,
                "must_int": True,
                "required": True,
                "jump_logic": {">=10": 5} # 时长>=10跳到第5题
            }
        ]
    }
    create_res = requests.post(f"{BASE_URL}/api/surveys/create", json=survey_payload).json()
    print("创建问卷结果:", create_res)
    survey_code = create_res["survey_url"].split('/')[-1]

    print("\n================ 3. 测试跳转逻辑引擎 ================")
    next_res = requests.post(f"{BASE_URL}/api/survey/next_question", json={
        "survey_code": survey_code,
        "current_q_id": 1,
        "answer": "大一"
    }).json()
    print("选'大一'后的下一题 (预期跳转到第 3 题):", next_res)

    print("\n================ 4. 测试提交校验规则 (故意输入非法数据) ================")
    invalid_sub = requests.post(f"{BASE_URL}/api/submissions/submit", json={
        "survey_code": survey_code,
        "username": "student_A",
        "answers": {
            "1": "大一",
            "3": 25 # 超过 24 小时最大限制
        }
    }).json()
    print("非法输入提交结果 (预期触发校验报错):", invalid_sub)

    print("\n================ 5. 测试正常提交答卷 ================")
    valid_sub1 = requests.post(f"{BASE_URL}/api/submissions/submit", json={
        "survey_code": survey_code,
        "username": "student_A",
        "answers": {"1": "大一", "3": 8}
    }).json()
    print("答卷1 提交结果:", valid_sub1)

    valid_sub2 = requests.post(f"{BASE_URL}/api/submissions/submit", json={
        "survey_code": survey_code,
        "username": "student_B",
        "answers": {"1": "大二", "2": ["VSCode", "Notion"], "3": 12}
    }).json()
    print("答卷2 提交结果:", valid_sub2)

    print("\n================ 6. 测试统计结果生成 ================")
    stats_res = requests.get(f"{BASE_URL}/api/survey/stats/{survey_code}").json()
    print("问卷统计结果:")
    print(json.dumps(stats_res, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    test_pipeline()