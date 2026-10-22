# MongoDB Schema 设计与数据模型说明

## 1. 项目概述

本项目基于 MongoDB（NoSQL）构建在线问卷系统。问卷结构具有高度灵活、题目类型多样（单选、多选、文本/数字填空）以及业务规则嵌套（校验规则、动态跳转逻辑）等特点。传统关系型数据库（RDBMS）通常需要设计多张表（如 `users`、`surveys`、`questions`、`options`、`jump_rules`、`submissions`），并通过复杂的外键与多表 JOIN 获取完整数据。

利用 MongoDB 的 JSON 文档模型（Document Model），可以将问卷的属性、题目、规则和跳转逻辑内嵌在单个文档中，从而提升读取效率与扩展能力。

## 2. 集合设计

系统数据库名称为 `survey_system`，包含以下三个核心集合：

| 集合 | 存储内容 |
| --- | --- |
| `users` | 系统用户/管理员信息 |
| `surveys` | 问卷元数据、题目内容、校验规则及动态跳转逻辑 |
| `submissions` | 用户提交的答卷数据 |

## 3. 集合结构定义

### 3.1 `users` 集合（用户数据）

用于账号认证与问卷权限隔离。每个用户登录后仅能管理自己创建的问卷。

#### JSON 示例

```json
{
  "_id": { "$oid": "653b211a0f823f0012345678" },
  "username": "zhangsan",
  "password": "hashed_or_plain_password_123",
  "created_at": { "$date": "2026-10-22T08:00:00Z" }
}
```

#### 字段说明

| 字段名 | 数据类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `_id` | ObjectId | 是 | 唯一主键 |
| `username` | String | 是 | 用户名（系统唯一，用于登录） |
| `password` | String | 是 | 登录密码 |
| `created_at` | Date | 是 | 账号注册时间 |

### 3.2 `surveys` 集合（问卷与题目规则）

这是系统的核心集合。采用内嵌文档数组（Embedded Array）结构，将题目（`questions`）、校验规则（`min_select`、`must_int` 等）与跳转逻辑（`jump_logic`）聚合在同一问卷文档内。

#### JSON 示例

```json
{
  "_id": { "$oid": "653b211a0f823f0012345679" },
  "survey_code": "10ae00d3",
  "survey_url": "/survey/10ae00d3",
  "title": "大学生生活习惯与学习调查",
  "description": "用于评估大学生日常学习时长与软件使用情况",
  "author": "zhangsan",
  "status": "published",
  "questions": [
    {
      "q_id": 1,
      "type": "single",
      "title": "你的年级是？",
      "options": ["大一", "大二", "大三", "大四"],
      "required": true,
      "jump_logic": {
        "大一": 3
      }
    },
    {
      "q_id": 2,
      "type": "multiple",
      "title": "常用的学习/开发软件",
      "options": ["Notion", "VSCode", "Anki", "GoodNotes"],
      "required": true,
      "min_select": 2,
      "max_select": 3
    },
    {
      "q_id": 3,
      "type": "number_blank",
      "title": "每天平均学习时长（小时）",
      "required": true,
      "min_val": 0,
      "max_val": 24,
      "must_int": true,
      "jump_logic": {
        ">=10": 5
      }
    },
    {
      "q_id": 4,
      "type": "text_blank",
      "title": "主要遇到的困惑与建议",
      "required": false,
      "min_len": 5,
      "max_len": 200
    }
  ],
  "created_at": { "$date": "2026-10-22T08:30:00Z" }
}
```

#### 问卷顶层字段

| 字段名 | 数据类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `_id` | ObjectId | 是 | 唯一主键 |
| `survey_code` | String | 是 | 问卷唯一短码（如 `10ae00d3`） |
| `survey_url` | String | 是 | 问卷访问路径（如 `/survey/10ae00d3`） |
| `title` | String | 是 | 问卷标题 |
| `description` | String | 否 | 问卷简介说明 |
| `author` | String | 是 | 关联创建者的 `username` |
| `status` | String | 是 | 状态：`draft`（草稿）、`published`（已发布）、`closed`（已关闭） |
| `questions` | Array | 是 | 嵌套的题目对象列表 |
| `created_at` | Date | 是 | 创建时间 |

#### 题目对象字段（`questions` 数组项）

| 字段名 | 数据类型 | 适用题型 | 说明 |
| --- | --- | --- | --- |
| `q_id` | Integer | 全部 | 问卷内题目序号（从 1 开始递增） |
| `type` | String | 全部 | 题型：`single`（单选）、`multiple`（多选）、`text_blank`（文本填空）、`number_blank`（数字填空） |
| `title` | String | 全部 | 题目名称 |
| `required` | Boolean | 全部 | 是否必答（`true`/`false`） |
| `options` | Array | 单选/多选 | 选项文本数组（如 `["A", "B", "C"]`） |
| `min_select` | Integer | 多选 | 最少选择项数校验规则 |
| `max_select` | Integer | 多选 | 最多选择项数校验规则 |
| `min_len` | Integer | 文本填空 | 最小字符长度限制 |
| `max_len` | Integer | 文本填空 | 最大字符长度限制 |
| `min_val` | Number | 数字填空 | 允许的数值最小值 |
| `max_val` | Number | 数字填空 | 允许的数值最大值 |
| `must_int` | Boolean | 数字填空 | 是否必须输入整数 |
| `jump_logic` | Object | 单选/数字填空 | 动态跳转规则表达式字典，映射格式为 `{ "答案条件": 目标q_id }` |

### 3.3 `submissions` 集合（答卷与统计数据）

存储用户填写的答案。采用键值映射（Key-Value Map）格式存储 `answers`，便于灵活对应不同类型的题目答案。

#### JSON 示例

```json
{
  "_id": { "$oid": "653b211a0f823f001234567a" },
  "survey_code": "10ae00d3",
  "username": "student_B",
  "answers": {
    "1": "大二",
    "2": ["VSCode", "Notion"],
    "3": 12,
    "4": "希望能多组织讲座。"
  },
  "submitted_at": { "$date": "2026-10-22T09:00:00Z" }
}
```

#### 字段说明

| 字段名 | 数据类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `_id` | ObjectId | 是 | 唯一主键 |
| `survey_code` | String | 是 | 所属问卷的唯一短码 |
| `username` | String | 否 | 答题人用户名（若为匿名提交可留空） |
| `answers` | Object | 是 | 题目答案映射。Key 为 `str(q_id)`；Value 为具体答案：单选/文本为 String，多选为 Array，数字填空为 Number |
| `submitted_at` | Date | 是 | 提交时间 |

## 4. 设计理由与架构优势

### 4.1 零 JOIN，高性能读取

在加载问卷页面与渲染答题引擎时，仅需一次 `db.surveys.findOne({survey_code: "..."})` 即可获得问卷信息、所有题目以及对应的内嵌跳转规则，无需多次表连接（JOIN），从而降低数据库 I/O 延迟。

### 4.2 规则扩展性强

不同题型的校验参数差异较大（多选有 `min_select`，数字填空有 `min_val`）。MongoDB 的无模式特征允许不同题目对象拥有不同属性，无须额外设计扩展字段或稀疏表。

### 4.3 聚合计算能力强

通过 MongoDB 聚合管道，可高效地针对 `submissions` 集合执行 `$group`、`$unwind`、`$avg`、`$max` 等聚合函数，几行命令即可算出选项百分比分布和数值平均分。

## 5. 数据库索引设计与优化建议

为保证大规模并发访问下的查询性能，建议创建以下索引。

### `users` 集合

**唯一索引：**

```javascript
db.users.createIndex({ "username": 1 }, { unique: true })
```

作用：确保用户名不重复，加速登录时的账号检索。

### `surveys` 集合

**唯一索引：**

```javascript
db.surveys.createIndex({ "survey_code": 1 }, { unique: true })
```

作用：加速通过唯一短码 `/survey/<survey_code>` 快速检索问卷。

**普通索引：**

```javascript
db.surveys.createIndex({ "author": 1 })
```

作用：加速“获取当前登录用户创建的问卷列表”的查询。

### `submissions` 集合

**复合索引：**

```javascript
db.submissions.createIndex({ "survey_code": 1, "submitted_at": -1 })
```

作用：根据问卷短码聚合统计答卷数据，或按提交时间倒序查看最新提交记录。
