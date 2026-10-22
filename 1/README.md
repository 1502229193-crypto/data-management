# 基于 MongoDB 的在线问卷系统（第一阶段）

本项目为《当代数据管理系统》大作业一（第一阶段）项目实现，采用 Python Flask + PyMongo + MongoDB 架构，支持用户注册登录、问卷管理、复杂数据校验、动态题目跳转以及数据聚合统计分析。

---

## 一、 项目文件结构

```text
当代数据管理系统/
└── 大作业/
    └── 1/
        ├── app.py           # 后端 Web API 服务与核心业务逻辑
        ├── test_all.py      # 自动化测试脚本（覆盖注册、登录、创建、跳转、校验与统计）
        ├── requirements.txt # 项目 Python 依赖库清单
        └── README.md        # 项目配置与运行说明文档
```

## 二、 环境准备

操作系统：macOS (Apple Silicon M芯片)
Python 环境：Python 3.x（推荐使用虚拟环境 ai_exp）
数据库：MongoDB (社区版)

### 1. 安装项目依赖

在终端中激活你的虚拟环境，并运行以下命令安装项目所需的依赖包：

```bash
pip install -r requirements.txt
```

（如果未配置 requirements.txt，也可直接执行：`pip install pymongo flask requests`）

## 三、 运行步骤

### 1. 启动本地 MongoDB 服务

打开终端，切换到项目根目录（含有 MongoDB 服务端可执行文件的路径），运行以下命令启动数据库：

```bash
./mongodb-server/bin/mongod --dbpath ./db-data
```

注意：保持该终端窗口处于打开状态，等待出现 `waiting for connections on port 27017` 的提示，说明数据库已就绪。

### 2. 启动 Flask 后端服务

新开一个终端窗口，切换到当前代码文件夹（大作业/1），激活 Python 虚拟环境后执行：

```bash
python app.py
```

终端输出以下提示即说明后端 Web 服务启动成功：

```text
✅ 数据库初始化完成！
🚀 正在启动后端 Web 服务...
 * Running on http://127.0.0.1:5000
```

## 四、 测试与验证

保持 app.py 服务运行，在另一个终端窗口中执行全流程自动化测试脚本：

```bash
python test_all.py
```

测试涵盖的主要功能：

- 用户认证：测试账号注册与登录 API。
- 问卷创建：创建带有单选、多选、数字填空规则及跳转逻辑的问卷。
- 跳转计算：验证单选/数字区间触发的动态题目跳转引擎。
- 后端校验：故意提交不符合要求的非法数据（如必答未填、数值超限），验证后端的错误拦截。
- 答卷提交：正常提交合法答卷并存入 MongoDB submissions 集合。
- 聚合统计：调用统计 API，查看选项频次分布及数字填空平均值。

## 五、 主要 API 接口列表

| 接口路径 | 请求方式 | 功能说明 |
| --- | --- | --- |
| `/api/register` | POST | 用户账号注册 |
| `/api/login` | POST | 用户账号登录 |
| `/api/surveys/create` | POST | 创建问卷（嵌入题目、校验规则与跳转逻辑） |
| `/api/surveys/list/<username>` | GET | 查看指定用户创建的问卷列表 |
| `/api/survey/<survey_code>` | GET | 获取问卷详情与题目结构 |
| `/api/survey/next_question` | POST | 动态跳转引擎：计算用户的下一题 ID |
| `/api/submissions/submit` | POST | 提交答卷与后端严格数据校验 |
| `/api/survey/stats/<survey_code>` | GET | 获取问卷聚合统计分析结果 |
