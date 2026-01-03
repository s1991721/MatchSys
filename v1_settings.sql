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
