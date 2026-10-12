# 租户数据库路由

登录账号必须为完整企业邮箱。登录中间件从邮箱提取域名，通过现有
`managed_schema()` 规则找到数据库，并验证该库的 `tenant_profile` 域名。
沿用 `matchsys_XXXX` 命名及旧租户命名兼容规则，不维护共享映射表。
未知租户、非法邮箱或不存在的数据库不会回退到原业务数据库。

成功登录后，服务端数据库会话记录 `tenant_domain`；浏览器使用 HttpOnly
签名 `matchsys_tenant` Cookie 携带该域名。路由中间件在 SessionMiddleware
之前选择租户，因此用户查询、登录审计和 `django_session` 均在租户库内。
所有后续 API 都校验会话与域名一致。可选 `X-Tenant-Domain` 请求头必须与
已认证租户相同，不能用它切换公司。退出会清理会话和域名 Cookie。

`project.tenancy` 使用 ContextVar 保存当前域名及实际 Schema。
`project.db.backends.tenant_mysql` 在建立数据库连接时读取上下文，覆盖
默认连接的目标数据库；ORM、`connection.cursor()`、动态年月表和
`transaction.atomic()` 均继续使用现有接口。上下文变化时关闭旧连接并
重新连接；事务内禁止切换租户。请求结束或异常会恢复上下文。
没有租户的业务 HTTP 请求不能访问默认数据库。独立的平台管理连接保留。

后台线程通过 `tenant_target()` 捕获创建线程时的上下文并在结束时关闭连接。
定时调度枚举已管理租户，为每家公司分别查询任务、执行并记录结果。
本机任务 HTTP 调用携带短期签名 token，绑定域名及任务路径；只允许现有
维护任务入口。外部 URL 不发送此 token。AI、LINE、激活及最近案件通知批次
缓存已按租户隔离。

LINE 回调地址需要附加 `?tenant_domain=company.com`，回调仍使用对应公司
配置中的 LINE secret 验证请求签名。旧登录会话没有域名绑定，需要重新登录。
原业务数据库仍显示“待接入”，未自动迁移；旧的非邮箱账号不再适用新登录入口。
原业务库的数据接入及文件存储隔离不是本次数据库路由改造内容。

验证：`ENABLE_SCHEDULER=false .venv/bin/python manage.py test project.test_tenancy`。
10 项测试覆盖上下文恢复、后台线程隔离、Cookie 签名、会话绑定、请求头
冲突、事务内禁止切换、连接重建、任务 token 路径绑定和配置缓存隔离。
另外使用两个临时 MySQL 租户验证登录、租户数据库会话、公司配置查询、
相同用户 ID、ORM 写入、原生 SQL、事务及退出；验证库均已清理。
