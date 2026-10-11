-- AI面试系统 MySQL 数据库及表结构初始化脚本。
--
-- 本脚本用于初始化，可重复执行，不删除现有业务数据。
-- CREATE TABLE IF NOT EXISTS 仅创建尚不存在的表，不更新已有表结构。
-- 升级已有数据库时，需要另行执行表结构迁移。
-- 业务表统一使用 deleted_at 标记软删除，NULL 表示未删除。
-- 表间不设置外键，关联关系由应用层校验。

/*!40101 SET NAMES utf8mb4 */;
SET character_set_client = utf8mb4;
SET character_set_connection = utf8mb4;
SET character_set_results = utf8mb4;

CREATE DATABASE IF NOT EXISTS `ai_interview`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- AI面试服务使用独立数据库账户，与 MatchSys 的数据库账户隔离。
-- 每次执行均将数据库账户密码设为下方指定值，并授予本库权限。
CREATE USER IF NOT EXISTS 'ai_interview_user'@'%'
    IDENTIFIED BY 'ai_interview_user_AbCdEfG';
ALTER USER 'ai_interview_user'@'%'
    IDENTIFIED BY 'ai_interview_user_AbCdEfG';

GRANT ALL PRIVILEGES ON `ai_interview`.* TO 'ai_interview_user'@'%';
FLUSH PRIVILEGES;

USE `ai_interview`;

-- Django 服务端会话存储。
-- 会话表由本 SQL 脚本初始化，无需通过 django_migrations 创建。
CREATE TABLE IF NOT EXISTS django_session
(
    session_key  VARCHAR(40) NOT NULL PRIMARY KEY,
    session_data LONGTEXT    NOT NULL,
    expire_date  DATETIME(6) NOT NULL,

    INDEX django_session_expire_date_a5c62663 (expire_date)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COMMENT = 'Django服务端会话表';


-- 企业账户：当前一个账户代表一家企业，登录账号唯一。
CREATE TABLE IF NOT EXISTS user_account
(
    id             BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '账户ID',

    username       VARCHAR(100) NOT NULL COMMENT '登录账号',
    password       VARCHAR(255) NOT NULL COMMENT '登录密码（现阶段明文）',
    display_name   VARCHAR(100) NOT NULL COMMENT '登录用户姓名',

    company_name   VARCHAR(200) NOT NULL COMMENT '公司名称',
    company_code   VARCHAR(100) NULL COMMENT '公司编码',

    created_by     BIGINT       NULL COMMENT '创建人账户ID（user_account.id）',
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by     BIGINT       NULL COMMENT '更新人账户ID（user_account.id）',
    updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at     DATETIME     NULL COMMENT '删除时间（软删除）',

    UNIQUE KEY uk_user_account_username (username)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
    COMMENT ='企业登录账户表';


-- 面试额度：每个账户对应一条余额记录，由应用层在创建账户时建立。
-- 创建邀请成功时扣除1次额度，创建邀请与扣减余额必须在同一事务中提交。
-- 额度不足时不创建邀请；使用条件扣减或行锁防止并发超扣。
CREATE TABLE IF NOT EXISTS user_quota
(
    id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '额度ID',
    user_id              BIGINT          NOT NULL COMMENT '账户ID',

    remaining_count      BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '剩余面试次数',

    created_by           BIGINT          NULL COMMENT '创建人账户ID（user_account.id）',
    created_at           DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by           BIGINT          NULL COMMENT '更新人账户ID（user_account.id）',
    updated_at           DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at         DATETIME     NULL COMMENT '删除时间（软删除）',

    UNIQUE KEY uk_user_quota_user_id (user_id)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
    COMMENT ='用户面试额度表';


-- 面试邀请：一条记录对应一位候选人的一次面试，统一使用日语。
-- 岗位、技能、评价目标及候选人信息保存为创建时的快照。
-- 邀请凭证仅保存SHA-256哈希，凭证哈希及请求标识均不设置唯一约束。
-- 状态与前端一致：“全部”仅为筛选选项，不保存为状态值。
-- 待参加且邀请到期时按已过期处理，已完成和异常状态不受有效期影响。
-- JSON结构、评价项目ID及权重合计100%由应用层校验。
CREATE TABLE IF NOT EXISTS interview
(
    id                      BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '面试ID',
    user_id                 BIGINT       NOT NULL COMMENT '所属企业账户ID',
    request_id              VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '创建请求标识，不强制唯一',
    invitation_token_hash   CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '邀请凭证SHA-256哈希',

    position_name           VARCHAR(200) NOT NULL COMMENT '岗位名称',
    work_description        TEXT         NOT NULL COMMENT '工作内容',
    position_requirements   TEXT         NULL COMMENT '岗位要求',
    skills                  JSON         NOT NULL COMMENT '技能名称及要求程度快照',
    assessment_targets      JSON         NOT NULL COMMENT '评价项目ID、名称、考察重点及权重快照，权重合计100%',
    duration_minutes        SMALLINT UNSIGNED NOT NULL DEFAULT 15 COMMENT '计划面试时长（分钟）',

    candidate_name          VARCHAR(100) NOT NULL COMMENT '候选人姓名',
    candidate_email         VARCHAR(255) NOT NULL COMMENT '候选人邮箱',

    status                  VARCHAR(32)  NOT NULL DEFAULT 'waiting' COMMENT '面试状态：waiting 待参加 / completed 已完成 / abnormal 异常 / expired 已过期',
    invite_expires_at       DATETIME     NOT NULL COMMENT '邀请有效截止时间',
    recording_storage_key   VARCHAR(1000) NULL COMMENT '音频对象存储文件标识',
    video_storage_key       VARCHAR(1000) NULL COMMENT '视频对象存储文件标识',

    created_by              BIGINT       NULL COMMENT '创建人账户ID（user_account.id）',
    created_at              DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by              BIGINT       NULL COMMENT '更新人账户ID（user_account.id）',
    updated_at              DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at              DATETIME     NULL COMMENT '删除时间（软删除）'
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
  COMMENT = 'AI面试邀请及运行记录表';


-- 面试报告：仅在生成成功后创建记录，失败信息保存在任务或日志中。
-- 每次面试最多对应一份报告，由应用层保证，不设置唯一约束。
-- 报告列表展示 generated_at；read_at 为NULL表示未读，首次阅读时写入。
CREATE TABLE IF NOT EXISTS interview_report
(
    id                 BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '报告ID',
    interview_id       BIGINT       NOT NULL COMMENT '面试ID',
    report_text        LONGTEXT     NULL COMMENT '报告正文',
    assessment_scores  JSON         NULL COMMENT '按评价项目ID关联的得分及评价',
    generated_at       DATETIME     NOT NULL COMMENT '报告生成完成时间',
    read_at            DATETIME     NULL COMMENT '首次阅读时间，NULL表示未读',
    created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at         DATETIME     NULL COMMENT '删除时间（软删除）'
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
  COMMENT = 'AI面试报告表';
