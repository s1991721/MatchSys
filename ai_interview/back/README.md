# AI 面试后端 API

前端接入说明见 `../front/README.md`。业务表由 `database/init_mysql.sql`
维护，ORM 模型均为 `managed=False`，不要用 Django migrations 创建业务表。
报告使用 ORM 关联查询，但 `db_constraint=False` 不会给现有表增加外键。

## 启动

安装 `requirements.txt`，初始化 SQL 后，在本目录运行：

```sh
python -m uvicorn config.asgi:application --host 127.0.0.1 --port 8001 --reload
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
| GET | `/reports` | 分页报告列表，`reading=all/unread/read`，可选 `interview_id` |
| GET | `/reports/{id}` | 报告详情，读取本身不改变未读状态 |
| POST | `/reports/{id}/read` | 标记首次阅读；重复操作保留原始 `read_at` |
| DELETE | `/reports/{id}` | 软删除报告 |

面试列表筛选：`status=all/waiting/completed/abnormal/expired/attention`；`query` 搜索
候选人姓名/邮箱；`from=YYYY-MM-DD`、`to=YYYY-MM-DD` 筛选创建日期（两端包含）。
`attention` 合并异常与过期记录，供首页异常分类使用，不存为面试状态。
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
候选人流程、Live 面试、录制与评价见后文；邮件发送仍待实现。

### 报告数据

列表返回 `id`、`interview_id`、`candidate_name`、`candidate_email`、`position_name`、
`generated_at`、`read_at`、`is_read`。详情额外返回 `report_text`、
`assessment_scores`、`assessment_targets`、`recording_storage_key`、`video_storage_key`。
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

## 候选人 Live 面试（2026-10-12）

候选人通过 16 位面试码或 `candidate.html?code=...` 进入，不使用企业 session。
创建和轮换返回同一面试码作为链接与手动输入凭证，忽略大小写、空格和连字符。
只保存邀请码 SHA-256，旧 token 链接不再支持。

本次实现遵循三条规则：

- AI 在同一次 Live 音频会话中提问、追问，并在结束时直接生成最终评价。
- 不保存逐轮对话文本，不启用输入转写，不接收浏览器提交的对话或评分。
- 前端录制候选人摄像头画面及双方声音，分片上传；后端保存录制和最终评价。

### 配置与启动

安装 `requirements.txt`，执行统一脚本 `database/init_mysql.sql`，用于新环境初始化或
为已有数据库补建缺失表。脚本也会按其中的配置重设数据库账户密码并授予权限，执行前确认账户配置。
`CREATE TABLE IF NOT EXISTS` 不修改已有表结构，已有表的字段变更仍需显式执行 `ALTER TABLE`。
新的 `interview_runtime` 表只有连接、录制、
异常原因和最终评价的暂存字段，没有对话文本字段。旧版 `interview_conversation` 不再读取或写入；
统一脚本不删除已有历史数据。

在 `back/.env` 或进程环境设置 `OPENAI_API_KEY`、`AI_INTERVIEW_REALTIME_MODEL`（默认 `gpt-realtime`）、
`AI_INTERVIEW_REALTIME_VOICE`（默认 `marin`）。进程环境优先，密钥不打包进镜像。
后端访问 OpenAI 时使用系统信任根并补充 `certifi` CA 证书，始终校验服务器证书和主机名。
更新后执行 `pip install -r requirements.txt` 并重启后端（开发模式自动重载除外）。
若签发短期凭证失败，后端日志会记录 HTTP 状态码或连接错误类别，不记录密钥、上游响应正文或面试内容。
当前流程没有文本评价模型、转写模型或 TTS 模型的单独调用。

在 `ai_interview/back` 下启动：

```sh
python -m uvicorn config.asgi:application --host 127.0.0.1 --port 8001 --reload
```

浏览器通过 WebRTC 直连 OpenAI，后端只提供 HTTP API。本地也可使用
`python manage.py runserver 127.0.0.1:8001`（PyCharm Django Server 配置同样可用）。
Dockerfile / Compose 继续使用 Uvicorn ASGI，提供后台超时巡检；HTTP 入口也会触发巡检。
Docker 后端只在内部网络暴露端口，信任 Nginx 转发的客户端 IP；Nginx 为本服务覆盖
X-Forwarded-For，避免候选人分片上传的限流全部算到代理 IP。
上线需要更新后端、前端与 Nginx 配置并重启。

### 面试状态与异常

`waiting → running → submitting → completed` 是正常流程。
候选人页面生成仅保存在内存中的随机 page_id，后端只保存其哈希。
刷新后 page_id 变化，验证入口立即把运行中的面试标记为 `abnormal`。
连接只允许建立一次，不允许重新连接或恢复历史；重复连接也按异常处理。
关闭页面、断线、AI 服务失败、录制失败或上传失败均终止为 abnormal。

前端每 5 秒通过 HTTP 续心跳，超过 20 秒失联即异常；尚未连接的启动阶段最多 90 秒，
结束后的评价与录制封存最多 120 秒。ASGI lifespan watchdog 每 5 秒检查，
服务重启后也会终止遗留失联会话。正常浏览器直接向 OpenAI 发送音频。
刷新 / pagehide 的 abort 通知只是补充，不能替代后端检测。

异常记录保存原因和终止时间，保留已收到的录制片段，清除尚未发布的正常评价。
原邀请不可再次开始，候选人看到异常页，重新安排需要新邀请。

### 实时语音与最终评价

浏览器通过 `POST /api/candidate/client-secret` 获取 60 秒有效的短期凭证和面试配置，
再使用 WebRTC 直接连接 `https://api.openai.com/v1/realtime/calls`。
正式 OPENAI_API_KEY 不返回浏览器，短期凭证只保存在内存中。每个邀请只签发一次。
音频不经过 Django，不再使用 `/api/candidate/live` 后端 WebSocket。

所有候选人接口携带 `code` 和仅在内存中的 `page_id`：

| POST 路径 | 用途 |
| --- | --- |
| `/api/candidate/client-secret` | 开始后获取短期凭证及最终评价工具配置 |
| `/api/candidate/heartbeat` | 每 5 秒续心跳，返回面试状态；到时转入 submitting |
| `/api/candidate/finish` | 结束面试，转入 submitting；重试不重复改变状态 |
| `/api/candidate/evaluation` | 提交 `evaluation: {summary, conclusion, scores}` |
| `/api/candidate/recording/chunk`、`seal` | 持续上传录制并封存（沿用原格式） |

前端控制日语面试、语义 VAD 和打断，在同一 OpenAI 会话结束后强制调用
`submit_interview_report`，取得工具参数并经 HTTP 提交后端。
后端校验目标覆盖性、分数范围、总结与结论；客户端结果不视为可信的服务端 AI 输出。
只有评价格式无效时在同一上下文重试一次，不从录像转写后评价。
模型上下文禁止静默截断；如上下文超限或评价失败，按异常处理。

最终评价不逐字引用对话，只总结岗位相关能力与依据，供招聘人员复核，不自动决定录用。
缺少考察依据的目标明确标注，不能将其 0 分当作能力差。
评价与录制均成功后，才原子写入报告并标记 completed。
前端忽略逐句转写和普通会话消息，不入库、写文件、打印日志或显示字幕。
OpenAI 会话自身仍有临时上下文，这不等同于本系统保存对话文本。

### 前端录制与上传

MediaRecorder 录制候选人视频和 WebAudio 混合音频（候选人 + 实际播放的 AI 声音），
每 5 秒上传。静音麦克风时相应录音也静音，AI 被打断后未播放的声音不会被录入。
录制格式优先 WebM（VP8/Opus），浏览器不支持时使用 MP4。

| POST 路径 | 行为 |
| --- | --- |
| `/api/candidate/verify` | 验证邀请及页面所有权，刷新按异常处理 |
| `/api/candidate/start` | 设备、录制准备与同意后开始，绑定 page_id |
| `/api/candidate/abort` | 辅助终止并记录异常原因 |
| `/api/candidate/recording/chunk` | multipart code/page_id/index/mime/chunk，幂等写入片段 |
| `/api/candidate/recording/seal` | 校验分片齐全，合并录制，正常流程中等待同会话评价 |

每片最多 8MB、单场最多 256MB / 256 片。分片用编号和 SHA-256 去重，乱序到达也按编号合并；
上传或封存遇到网络错误及 5xx 响应时，前端以相同内容重试一次；4xx 错误直接终止，不重复请求。
首片校验容器标记。文件保存在 `MEDIA_ROOT/interviews/面试ID/运行标识/`，没有公开静态路由。
正常录制包含视频与双方音频的一份文件，DB 的音频与视频 key 指向同一录制，避免复制两份。
异常时未上传的最后片段可能丢失，后端已收到的片段保留在 parts 目录及运行元数据中。

企业报告详情返回受 session 保护的播放 URL：`GET /api/interviews/{id}/recording`。
播放入口校验企业归属、软删除状态，支持 HTTP Range；不能靠存储路径公开访问。
企业面试详情额外返回 started_at、ended_at、abnormal_reason、recording_state。
旧的候选人 room/turn/speech/evaluate/submit 入口已删除。

### 验证

项目根目录运行：

```sh
.venv/bin/python ai_interview/back/tests/candidate_contract.py
.venv/bin/python ai_interview/back/tests/finalization_contract.py
.venv/bin/python ai_interview/back/tests/browser_contract.py
node ai_interview/back/tests/candidate_frontend.cjs
node ai_interview/back/tests/voice_frontend.cjs
node ai_interview/back/tests/recording_frontend.cjs
node ai_interview/back/tests/live_audio.cjs
.venv/bin/python ai_interview/back/manage.py check
```

自动测试隔离数据库，使用模拟 Realtime 事件与录制分片，不调用真实 API。
配置有效密钥后需联调同会话评价、真实浏览器音视频录制与播放、刷新 / 断网异常，
及结束阶段最后音频和最后录制分片的保存。

WebRTC 与短期凭证接口参考：[OpenAI 官方文档](https://developers.openai.com/api/docs/guides/realtime-webrtc)。
