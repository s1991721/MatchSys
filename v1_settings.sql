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

INSERT INTO matchSys.sys_settings (name, settings, created_by, created_at, updated_by, updated_at, deleted_at)
VALUES ('match', '{"cycle_days": 14}', 1, '2026-01-03 17:08:42', 1, '2026-01-04 14:01:59', NULL),
       ('ai', '{"api_key": "", "mode_type": "local", "model_name": "llama3.2:3b-instruct-q4_K_M"}', 1,
        '2026-01-04 05:31:02', 1, '2026-01-04 05:42:31', NULL);
