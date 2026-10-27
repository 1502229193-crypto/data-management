# MongoDB Schema 设计与数据模型说明（Phase 2 演进版）

## 1. 项目概述

本项目基于 MongoDB（NoSQL）构建在线问卷系统。在进入 **Phase 2** 后，系统引入了**全局独立题库、多版本控制、题目分享协作、防篡改锁定以及跨问卷聚合统计**等高级特性。

相比于 Phase 1 的完全内嵌模式，Phase 2 采用了**混合引用与版本链设计**。题目从问卷中剥离并独立存入全局题库集合，问卷通过引用特定的题目 ID 与版本号进行绑定，既实现了常用题目的高效复用与团队共享，又确保了已发布历史问卷的数据安全性与不可篡改性。

---

## 2. 核心集合设计

系统数据库名称为 `survey_system`，包含以下四个核心集合：

| 集合名称 | 存储内容说明 |
| --- | --- |
| `users` | 系统用户信息，用于账号认证与权限隔离 |
| `questions` | **【Phase 2 新增】** 全局独立题库，存储题目元数据、校验规则、版本链（`version`/`parent_id`）及共享权限（`shared_with`） |
| `surveys` | 问卷元数据。采用引用机制，记录题目 ID（`question_id`）与锁定版本（`version`） |
| `submissions` | 用户提交的答卷数据，通过题目 ID 映射对应的答案 |

---

## 3. 集合结构定义与 JSON 示例

### 3.1 `users` 集合（用户数据）

用于账号认证与问卷、题目的权限隔离。

#### JSON 示例

```json
{
  "_id": { "$oid": "653b211a0f823f0012345678" },
  "username": "teacher_zhang",
  "password": "hashed_or_plain_password_123",
  "created_at": { "$date": "2026-10-27T08:00:00Z" }
}

```

---

### 3.2 `questions` 集合（全局题库与版本控制 - Phase 2 核心）

独立存储所有题目，支持多版本并存、修改历史溯源、团队共享与防篡改锁定。

#### JSON 示例

```json
{
  "_id": { "$oid": "6ae0acc512b0d8934084ecbe" },
  "title": "你的年龄",
  "type": "number_blank",
  "min_val": 0,
  "max_val": 100,
  "must_int": true,
  "required": true,
  "jump_logic": { ">=10": 5 },
  
  // Phase 2 新增：版本与生命周期字段
  "version": 1,                      // 当前题目版本号
  "parent_id": null,                 // 版本溯源：若由旧题演变而来，指向旧题 _id
  "is_locked": true,                 // 防篡改锁：已被已发布问卷引用时置为 true，禁止直接修改
  
  // Phase 2 新增：权限与协作共享字段
  "owner": "teacher_zhang",          // 创建者用户名
  "shared_with": ["student_li"],     // 共享给其他协同用户的名单
  
  "created_at": { "$date": "2026-10-27T08:10:00Z" }
}

```

#### 字段说明

| 字段名 | 数据类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `_id` | ObjectId | 是 | 题目唯一主键 |
| `title` | String | 是 | 题目名称/内容 |
| `type` | String | 是 | 题型：`single`、`multiple`、`text_blank`、`number_blank` |
| `version` | Integer | 是 | 题目版本号（从 1 开始递增） |
| `parent_id` | String/Null | 否 | 上一个版本的题目 ID（构成 `v1 -> v2 -> v3` 版本链） |
| `is_locked` | Boolean | 是 | 锁定状态。若为 `true`，代表已被发布问卷引用，不可直接编辑原题 |
| `owner` | String | 是 | 题目的所有者账号 |
| `shared_with` | Array | 是 | 被分享授权的用户名列表 |

---

### 3.3 `surveys` 集合（问卷表 - 采用引用与版本锁定设计）

问卷不再内嵌完整的题目大对象，而是通过 `question_id` 与特定 `version` 进行安全引用。

#### JSON 示例

```json
{
  "_id": { "$oid": "653b211a0f823f0012345679" },
  "survey_code": "5b49b4a7",
  "survey_url": "/survey/5b49b4a7",
  "title": "2025年度调查问卷",
  "description": "用于期末教学评估",
  "author": "teacher_zhang",
  "status": "published",
  "questions": [
    {
      "question_id": "6ae0acc512b0d8934084ecbe",
      "version": 1,                     // 锁定引用的具体版本，确保后续题库改版不影响旧问卷
      "sort_order": 1
    }
  ],
  "created_at": { "$date": "2026-10-27T08:30:00Z" }
}

```

---

### 3.4 `submissions` 集合（答卷与统计数据）

存储用户针对问卷填写的实际答案。

#### JSON 示例

```json
{
  "_id": { "$oid": "653b211a0f823f001234567a" },
  "survey_code": "5b49b4a7",
  "username": "user1",
  "answers": {
    "6ae0acc512b0d8934084ecbe": 20
  },
  "submitted_at": { "$date": "2026-10-27T09:00:00Z" }
}

```

---

## 4. Phase 2 架构演进的设计优势

### 4.1 题目独立复用与团队共享

题目脱离了单一问卷的束缚。教师或管理员创建的常用题可以直接沉淀在全局 `questions` 题库中，并可通过 `shared_with` 安全地共享给团队成员（如学生或其他同事）跨问卷调用。

### 4.2 历史版本隔离与防篡改（解决数据污染）

通过 `is_locked` 锁机制与版本链（`version` + `parent_id`）：

* 已发布的历史问卷引用的题目版本保持不变，彻底避免了“改了题导致旧问卷数据失效”的问题。
* 当需要修改题目时，系统强制引导用户衍生新版本（$v1 \to v2$），不同问卷可自由选择引用旧版或新版。

### 4.3 强大的引用追踪与跨问卷聚合统计

* **引用追踪**：通过反向检索问卷集合（`db.surveys.find({"questions.question_id": q_id})`），管理员在修改或删除题目时可清晰知晓该题正被哪些问卷所使用。
* **跨问卷全局统计**：突破了传统问卷系统只能单表统计的局限。通过多问卷短码聚合（`$in` 查询），可一键统计某一道常用题在所有不同问卷中的总体回答分布与数理特征（如平均分、极值）。

---

## 5. 数据库索引设计与优化建议

为保证全局题库检索、版本溯源及跨问卷聚合时的响应性能，建议创建以下索引：

### `questions` 集合

```javascript
db.questions.createIndex({ "owner": 1 })
db.questions.createIndex({ "shared_with": 1 })

```

作用：加速用户查询自己创建的题目或被分享的协作题目。

### `surveys` 集合

```javascript
db.surveys.createIndex({ "survey_code": 1 }, { unique: true })
db.surveys.createIndex({ "questions.question_id": 1 })

```

作用：唯一索引加速问卷短码访问；复合索引加速**引用追踪**查询。

### `submissions` 集合

```javascript
db.submissions.createIndex({ "survey_code": 1, "submitted_at": -1 })

```

作用：加速答卷提交与单问卷/跨问卷统计分析的数据检索。