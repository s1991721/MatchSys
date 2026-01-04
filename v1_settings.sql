CREATE TABLE sys_settings
(
    id         BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    name       VARCHAR(255) NOT NULL COMMENT '配置名称（唯一）',
    settings   JSON         NOT NULL COMMENT '配置内容（JSON）',
    created_by BIGINT       NULL COMMENT '创建人ID',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by BIGINT       NULL COMMENT '更新人ID',
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at DATETIME     NULL COMMENT '删除时间（软删）'
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='系统设置表';

INSERT INTO sys_settings (name, settings, created_by, created_at, updated_by, updated_at, deleted_at)
VALUES ('match', '{"cycle_days": 14}', 1, '2026-01-03 17:08:42', 1, '2026-01-04 14:01:59', NULL),
       ('ai', '{"api_key": "", "mode_type": "local", "model_name": "llama3.2:3b-instruct-q4_K_M"}', 1,
        '2026-01-04 05:31:02', 1, '2026-01-04 05:42:31', NULL);


CREATE TABLE sys_tasks
(
    id          BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    name        VARCHAR(255) NOT NULL DEFAULT '' COMMENT '任务名称',
    time        TIME         NULL COMMENT '执行时间',
    frequency   VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '执行频率',
    cron_expr   VARCHAR(100) NOT NULL DEFAULT '' COMMENT 'Cron 表达式',
    method      VARCHAR(10)  NOT NULL DEFAULT 'POST' COMMENT '请求方式',
    api         VARCHAR(500) NOT NULL DEFAULT '' COMMENT 'API 地址',
    body        TEXT         NOT NULL COMMENT '请求参数 / Body',
    enabled     TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '是否启用',
    last_run_at DATETIME     NULL COMMENT '上次执行时间',
    next_run_at DATETIME     NULL COMMENT '下次执行时间',
    last_status VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '上次执行状态',
    last_error  TEXT         NOT NULL COMMENT '上次错误信息',
    created_by  BIGINT       NULL COMMENT '创建人ID',
    created_at  DATETIME     NOT NULL COMMENT '创建时间',
    updated_by  BIGINT       NULL COMMENT '更新人ID',
    updated_at  DATETIME     NOT NULL COMMENT '更新时间',
    deleted_at  DATETIME     NULL COMMENT '删除时间（软删）'
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='定时任务';


