-- AI Interview database/schema bootstrap for MySQL.
--
-- This script is intentionally non-destructive and can be run more than once.

/*!40101 SET NAMES utf8mb4 */;
SET character_set_client = utf8mb4;
SET character_set_connection = utf8mb4;
SET character_set_results = utf8mb4;

CREATE DATABASE IF NOT EXISTS `ai_interview`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `ai_interview`;

-- One account represents one company in the first release.
CREATE TABLE IF NOT EXISTS user_account
(
    id             BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '账户ID',

    username       VARCHAR(100) NOT NULL COMMENT '登录账号',
    password       VARCHAR(255) NOT NULL COMMENT '登录密码哈希',
    display_name   VARCHAR(100) NOT NULL COMMENT '登录用户姓名',

    company_name   VARCHAR(200) NOT NULL COMMENT '公司名称',
    company_code   VARCHAR(100) NULL COMMENT '公司编码',

    created_by     BIGINT       NULL COMMENT '创建人 user_account.id',
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by     BIGINT       NULL COMMENT '更新人 user_account.id',
    updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at     DATETIME     NULL COMMENT '删除时间（软删除）',

    UNIQUE KEY uk_user_account_username (username)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
    COMMENT ='企业登录账户表';


-- Each account has exactly one quota row. Recharge and consumption must be
-- updated in a database transaction to avoid concurrent over-consumption.
CREATE TABLE IF NOT EXISTS user_quota
(
    id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '额度ID',
    user_id              BIGINT          NOT NULL COMMENT '账户ID',

    remaining_count      BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '当前可用次数',

    created_by           BIGINT          NULL COMMENT '创建人 user_account.id',
    created_at           DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by           BIGINT          NULL COMMENT '更新人 user_account.id',
    updated_at           DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at           DATETIME        NULL COMMENT '删除时间（软删除）',

    UNIQUE KEY uk_user_quota_user_id (user_id)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
    COMMENT ='用户面试额度表';


-- Candidate, position, interview content and AI result are intentionally kept
-- in one table for the first release. They can be normalized when reuse or
-- report versioning becomes a concrete requirement.
CREATE TABLE IF NOT EXISTS interview
(
    id                    BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '面试ID',
    user_id               BIGINT       NOT NULL COMMENT '所属企业账户ID',

    interview_title       VARCHAR(200) NOT NULL COMMENT '面试标题',
    interview_link        VARCHAR(1000) NULL COMMENT '候选人访问的面试链接',
    interview_description TEXT         NOT NULL COMMENT '面试内容及要求，用于生成AI面试提示词',
    assessment_points     JSON         NOT NULL COMMENT '面试考查点及评分标准',
    assessment_scores     JSON         NULL COMMENT 'AI生成的各考查点得分及评价',
    overall_score         DECIMAL(5, 2) NULL COMMENT '面试总分',

    candidate_name        VARCHAR(100) NOT NULL COMMENT '候选人姓名',
    candidate_email       VARCHAR(255) NULL COMMENT '候选人邮箱',
    candidate_phone       VARCHAR(30)  NULL COMMENT '候选人电话',
    resume_url            VARCHAR(1000) NULL COMMENT '简历文件地址',

    status                VARCHAR(32)  NOT NULL DEFAULT 'draft' COMMENT 'draft / invited / in_progress / interrupted / completed / failed / cancelled',

    invite_expires_at     DATETIME     NULL COMMENT '邀请失效时间',

    created_by            BIGINT       NULL COMMENT '创建人 user_account.id',
    created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by            BIGINT       NULL COMMENT '更新人 user_account.id',
    updated_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at            DATETIME     NULL COMMENT '删除时间（软删除）'
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
    COMMENT ='AI面试表';
