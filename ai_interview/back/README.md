# AI 面试后端 API（第一阶段 review）

本阶段仅实现后端，不修改 `ai_interview/front`。业务表由 `database/init_mysql.sql`
维护，ORM 模型均为 `managed=False`，不要用 Django migrations 创建业务表。
报告使用 ORM 关联查询，但 `db_constraint=False` 不会给现有表增加外键。

## 启动

安装 `requirements.txt`，初始化 SQL 后，在本目录运行：

```sh
python manage.py runserver 8000
```

企业账户创建、初始额度及后续额度发放由其他功能模块负责，本后端使用已有的
`user_account` 和 `user_quota` 数据，不提供开户或额度设置管理命令。
额度只提供企业端读取接口，创建邀请时按事务扣减。
账户缺少有效额度记录时，创建邀请返回 `quota_unavailable`，需由负责额度的模块补齐。
账户更新沿用现有显示名和密码接口，公司资料目前只读。

数据库连接沿用 `AI_INTERVIEW_DB_NAME/USER/PASSWORD/HOST/PORT` 环境变量。
生产请配置 `AI_INTERVIEW_SECRET_KEY`、`AI_INTERVIEW_DEBUG=false`、`ALLOWED_HOSTS`，以及
跨域部署需要的 `AI_INTERVIEW_CORS_ALLOWED_ORIGINS`。

## 通用约定

- 路径前缀 `/api/`，带或不带末尾 `/` 均支持。
- JSON 请求体；成功 `{ "success": true, "data": {...} }`，业务错误
  `{ "success": false, "error": { "code": "...", "message": "..." } }`。
- 企业接口使用 Django session cookie，所有查询/修改只访问当前企业数据。
  请求中的 `user_id`、余额、审计字段、运行状态等不可写。
- 修改操作必须带 `X-CSRFToken`，先 GET `/api/me` 或 `/api/csrf` 获取
  `data.csrf_token`，同时保留 cookie；跨域请求设置 `credentials: 'include'`。
  现有 `/login` 为兼容本阶段未修改的前端暂时保留 CSRF 豁免。
- 时间以带时区 ISO 8601 返回，日期筛选和首页“今日”使用 Asia/Tokyo。
- 列表参数 `page=1`、`page_size=20`（1–100）；返回
  `{items: [...], total, page, page_size}`，按时间及 ID 降序稳定排序。
- 400 参数错误，401 未认证，404 不存在或属于其他企业，409 业务冲突，
  403 CSRF 校验失败，405 不支持的方法。

## 企业接口

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| POST | `/login` | 现有登录，参数 `user_name`、`password` |
| GET | `/me` | 当前账户及 CSRF token |
| GET | `/csrf` | 获取 CSRF token，可在登录前使用 |
| POST | `/logout` | 清除当前 session |
| POST | `/account` | 现有显示名/密码修改 |
| GET | `/quota` | `remaining_count`、`configured` |
| GET | `/dashboard` | 企业统计和未读报告数 |
| GET | `/interviews` | 分页面试列表 |
| POST | `/interviews` | 创建邀请并扣减一次额度 |
| GET | `/interviews/{id}` | 面试快照详情 |
| PATCH | `/interviews/{id}` | 修改未过期的待参加面试 |
| DELETE | `/interviews/{id}` | 软删除面试及关联报告，不返还额度 |
| POST | `/interviews/{id}/invitation` | 重新生成凭证，旧链接失效，不扣额度，不延长有效期 |
| GET | `/reports` | 分页报告列表，`reading=all/unread/read` |
| GET | `/reports/{id}` | 报告详情，读取本身不改变未读状态 |
| POST | `/reports/{id}/read` | 标记首次阅读；重复操作保留原始 `read_at` |
| DELETE | `/reports/{id}` | 软删除报告 |

面试列表筛选：`status=all/waiting/completed/abnormal/expired`；`query` 搜索
候选人姓名/邮箱；`from=YYYY-MM-DD`、`to=YYYY-MM-DD` 筛选创建日期（两端包含）。
待参加记录超过有效期时，查询、统计和编辑判断均视为 expired；completed/abnormal
不受有效期影响。GET 不会为过期状态修改数据库。

`/dashboard` 返回 `total_interviews`、`today_created`、`waiting`、`completed`、
`abnormal`、`expired`、`unread_reports`。SQL 没有实际开始/完成时间或 running 状态，
因此“今日”统计定义为今日创建，不虚构面试运行数据。

### 创建请求示例

```json
{
  "request_id": "5cc2639f-5b7d-4f57-8870-2318cae9b4a6",
  "position_name": "バックエンドエンジニア",
  "work_description": "業務システムの開発",
  "position_requirements": "開発経験3年以上",
  "skills": [{"name": "Python", "level": "advanced"}],
  "assessment_targets": [
    {"id": "coding", "name": "実装能力", "detail": "境界条件と問題分析", "weight": 100}
  ],
  "duration_minutes": 15,
  "candidate_name": "山田 太郎",
  "candidate_email": "candidate@example.com",
  "validity_days": 7
}
```

- 日语固定，当前时长固定 15 分钟，有效期为 1–30 天。
- 技能和评价目标各 1–20 项，技能等级 basic/proficient/advanced。
- 评价 ID 是 1–100 字符字符串，同一面试内唯一；省略时生成 `target-1` 等 ID。
  后续评分使用创建响应中的 ID。权重为 1–100 的整数且合计 100。
- 岗位名称最多 200 字符，候选人姓名/技能名/目标名最多 100，工作内容及要求
  最多 10000，目标重点最多 1000，邮箱最多 255 并校验格式。
- `request_id` 是企业内创建请求标识（1–100 ASCII 字符），建议 UUID。
  以额度行锁串行检查重复请求并扣减，余额不足不创建，插入失败回滚扣减。
  重复请求返回 409 `duplicate_request`，已软删除的请求标识也不能重用。
  重试不会重复扣费，但不会重放原凭证；需查询列表并重新生成邀请链接。
- 创建返回 201，`data` 含 `interview`、`invitation_token`、`invitation_url`、
  `remaining_count`。只存 SHA-256 哈希，列表/详情不返回哈希或原始凭证。
- PATCH 允许创建示例中的快照字段，不允许修改 `request_id`、`validity_days`，
  修改后仍校验完整快照。终态或过期面试返回 409。

`AI_INTERVIEW_INVITATION_BASE_URL` 指定候选人页面 URL 前缀，生成格式为
`{前缀}/{token}`，开发默认 `http://localhost:8000/interview`。
**本阶段不包含候选人页面、凭证兑换/开始面试、AI 对话、邮件发送、媒体上传或实际报告生成**；
生成 URL 是后续候选人入口使用的接口契约，当前不能直接开始面试。

### 报告数据

列表返回 `id`、`interview_id`、`candidate_name`、`candidate_email`、`position_name`、
`generated_at`、`read_at`、`is_read`。详情额外返回 `report_text`、
`assessment_scores`、`recording_storage_key`、`video_storage_key`。
报告列表时间取 SQL 的 `generated_at`，不将它冒充实际面试完成时间。
媒体只返回对象存储 key，不拼接未经授权的公开 URL；签名播放 URL 接入留待存储服务确定。

## 可信服务写入接口

配置 `AI_INTERVIEW_SERVICE_KEY`，仅后台 worker 持有，通过 `X-Service-Key` 传入。
未配置时入口关闭；不能把该密钥交给浏览器。此类入口独立于企业 session，豁免 CSRF。

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| PATCH | `/internal/interviews/{id}` | 写入 completed/abnormal 及录音/视频 key |
| PUT | `/internal/interviews/{id}/report` | 创建或更新成功报告 |

运行更新示例：

```json
{"status": "completed", "recording_storage_key": "interviews/1/audio.wav"}
```

completed/abnormal 为终态，仅允许重复写入相同状态，不能互相切换。
媒体 key 最多 1000 字符。状态终止时间不另存，因为现有 SQL 没有对应字段。

报告请求：

```json
{
  "report_text": "面接評価レポート正文",
  "assessment_scores": [{"id": "coding", "score": 90, "evaluation": "良好"}]
}
```

只允许给 completed 面试写入报告，评分必须逐项覆盖评价目标且不能重复或添加未知 ID，
分数为 0–100 整数。正文必填、最多 1000000 字符；单项评价最多 10000 字符。
锁定父面试行，保证并发写入仍只有一份报告；报告软删除后再次写入恢复原记录。
首次创建 201、更新 200；内容变化时刷新 generated_at 并清除 read_at，
相同内容的重复提交保持时间和阅读状态。失败时不创建空报告。
