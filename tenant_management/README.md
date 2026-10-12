# 租户管理（第一阶段）

入口：`/tenant-management/login/`；管理首页：`/tenant-management/`。

固定平台账号：`platform_admin`；初始密码：`MatchSys@2026`。
账号和密码哈希在 `credentials.py` 中维护，不使用数据库账号表。
部署前更换密码哈希，更改固定凭据会使已有平台会话失效。

平台使用独立的 `matchsys_platform_session` Cookie 和 Django 文件会话，
不使用公司业务数据库，也不赋予公司用户登录身份。退出时删除服务端会话。
文件会话默认使用系统临时目录；生产环境应配置受保护、可写的
`SESSION_FILE_PATH`，多实例部署需要共享该目录。使用 HTTPS 时启用
`SESSION_COOKIE_SECURE`。过期会话文件可通过 Django `clearsessions` 清理。

本阶段没有租户创建、数据库初始化、公司管理员初始化或业务数据库路由。
