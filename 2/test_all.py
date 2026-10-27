import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_phase2_pipeline():
    print("================ 1. 测试用户注册与登录 ================")
    requests.post(f"{BASE_URL}/api/register", json={"username": "teacher_zhang", "password": "123"})
    requests.post(f"{BASE_URL}/api/register", json={"username": "student_li", "password": "123"})
    print("用户注册登录准备就绪。")

    print("\n================ 2. 测试独立题库创建（教师创建常用题） ================")
    q1_res = requests.post(f"{BASE_URL}/api/questions/create", json={
        "title": "你的年龄",
        "type": "number_blank",
        "min_val": 0,
        "max_val": 100,
        "must_int": True,
        "author": "teacher_zhang"
    }).json()
    print("创建题目1结果:", q1_res)
    q1_id = q1_res["question_id"]

    q2_res = requests.post(f"{BASE_URL}/api/questions/create", json={
        "title": "常用开发工具",
        "type": "multiple",
        "options": ["VSCode", "PyCharm", "Eclipse"],
        "min_select": 1,
        "max_select": 2,
        "author": "teacher_zhang"
    }).json()
    print("创建题目2结果:", q2_res)
    q2_id = q2_res["question_id"]

    print("\n================ 3. 测试题目分享给团队成员 ================")
    share_res = requests.post(f"{BASE_URL}/api/questions/share", json={
        "question_id": q1_id,
        "owner": "teacher_zhang",
        "target_user": "student_li"
    }).json()
    print("题目分享结果:", share_res)

    print("\n================ 4. 测试基于旧题创建新版本 (v1 -> v2) ================")
    ver_res = requests.post(f"{BASE_URL}/api/questions/version/" + q1_id, json={
        "title": "你的真实年龄（精确到岁）",
        "author": "teacher_zhang"
    }).json()
    print("衍生新版本结果:", ver_res)
    q1_v2_id = ver_res["new_question_id"]

    print("\n================ 5. 测试引用题库创建问卷（问卷A用旧版，问卷B用新版） ================")
    survey_a_res = requests.post(f"{BASE_URL}/api/surveys/create", json={
        "title": "2025年度调查问卷",
        "author": "teacher_zhang",
        "questions": [
            {"question_id": q1_id, "version": 1, "sort_order": 1},
            {"question_id": q2_id, "version": 1, "sort_order": 2}
        ]
    }).json()
    print("问卷A创建结果:", survey_a_res)
    survey_a_code = survey_a_res["survey_url"].split('/')[-1]

    survey_b_res = requests.post(f"{BASE_URL}/api/surveys/create", json={
        "title": "2026年度升级问卷",
        "author": "teacher_zhang",
        "questions": [
            {"question_id": q1_v2_id, "version": 2, "sort_order": 1}
        ]
    }).json()
    print("问卷B创建结果:", survey_b_res)
    survey_b_code = survey_b_res["survey_url"].split('/')[-1]

    print("\n================ 6. 测试引用追踪（查看 '你的年龄' 被哪些问卷使用） ================")
    usage_res = requests.get(f"{BASE_URL}/api/questions/usages/{q1_id}").json()
    print("题目引用追踪结果:", json.dumps(usage_res, ensure_ascii=False, indent=2))

    print("\n================ 7. 测试提交答卷 ================")
    requests.post(f"{BASE_URL}/api/submissions/submit", json={
        "survey_code": survey_a_code,
        "username": "user1",
        "answers": {q1_id: 20, q2_id: ["VSCode"]}
    })
    requests.post(f"{BASE_URL}/api/submissions/submit", json={
        "survey_code": survey_b_code,
        "username": "user2",
        "answers": {q1_v2_id: 22}
    })
    print("答卷提交完毕。")

    print("\n================ 8. 测试跨问卷题目全局统计分析 ================")
    global_stats = requests.get(f"{BASE_URL}/api/questions/stats/{q1_id}").json()
    print("跨问卷全局统计结果:")
    print(json.dumps(global_stats, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    test_phase2_pipeline()