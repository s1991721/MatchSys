CREATE TABLE IF NOT EXISTS wrong_mail_info (
    id              VARCHAR(255)  PRIMARY KEY,
    title           VARCHAR(500)  COMMENT '邮件标题',
    address         VARCHAR(255)  NOT NULL COMMENT '发件人',
    body            TEXT          COMMENT '正文内容',
    files           TEXT          COMMENT '附件信息',
    date            DATETIME      COMMENT '日期',
    remark          VARCHAR(500)  COMMENT '备注',
    country         VARCHAR(100)  COMMENT '国家 0=日本籍 1=日本籍以外',
    skills          VARCHAR(500)  COMMENT '技能要求',
    price           DECIMAL(10, 2) COMMENT '价格',

    wrong_type      TINYINT(1)    COMMENT '错误类型 1=邮件分类错误 2=国籍识别错误 3=关键词识别错误',
    wrong_label     TINYINT(1)    COMMENT '错误分类',
    correct_label   TINYINT(1)    COMMENT '正确分类',
    deleted_at      DATETIME      COMMENT '下载标记时间（软删除）'
)
COMMENT = '错误邮件记录表';

SET @add_mail_project_cc = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE mail_project_info ADD COLUMN cc VARCHAR(1024) NOT NULL DEFAULT '''' COMMENT ''抄送'' AFTER address',
        'SELECT 1'
    )
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'mail_project_info'
      AND COLUMN_NAME = 'cc'
);
PREPARE stmt FROM @add_mail_project_cc;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_mail_technician_cc = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE mail_technician_info ADD COLUMN cc VARCHAR(1024) NOT NULL DEFAULT '''' COMMENT ''抄送'' AFTER address',
        'SELECT 1'
    )
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'mail_technician_info'
      AND COLUMN_NAME = 'cc'
);
PREPARE stmt FROM @add_mail_technician_cc;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;


INSERT INTO sys_settings (name, settings, created_by, created_at, updated_by, updated_at, deleted_at) VALUES
    ('mail-template','{"anjian": "いつもお世話になっております。\\n株式会社の林でございます。\\n\\n技術者をご紹介いただきありがとうございます。\\n弊社にて対応可能な案件をご紹介させて頂きます。\\nご検討頂けますと幸いです。\\n\\n**************************************\\n{project_block}\\n{detail_block}\\n{requirement_block}\\n{skills_must_block}\\n{skills_can_block}\\n{remark_block}\\n**************************************\\n\\n今後とも何卒よろしくお願い申し上げます。\\n\\n＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝\\n株式会社\\n営業部　マネージャー：\\n個人mail:gmail@outlook.com\\n営業共通mail: outlook@gmail.com\\nmobile: 010-2345-6789\\n〒123-4567\\n東京都XXX区XX町X丁目12-3\\n第一 ビル 88F\\nHP:https://www.homapage.jp/\\n", "technician": "いつもお世話になっております。\\n株式会社の林でございます。\\n\\n技術者をご紹介させて頂きます。\\nご検討頂けますと幸いです。\\n\\n**************************************\\n{person_intro}\\n**************************************\\n\\n今後とも何卒よろしくお願い申し上げます。\\n\\n＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝\\n株式会社\\n営業部　マネージャー：\\n個人mail:gmail@outlook.com\\n営業共通mail: outlook@gmail.com\\nmobile: 010-2345-6789\\n〒123-4567\\n東京都XXX区XX町X丁目12-3\\n第一 ビル 88F\\nHP:https://www.homapage.jp/\\n"}',1,'2026-04-22 15:10:29',NULL,'2026-04-22 15:13:25',NULL);

UPDATE sys_settings
SET settings = JSON_SET(
        settings,
        '$.order',
        '{company_name}\nご担当者様\n\nいつもお世話になっております。\n\n注文書を添付にて送付いたします。\n内容をご確認のうえ、ご査収くださいますようお願いいたします。\n\nご不明点や修正がございましたら、お知らせください。\n何卒よろしくお願いいたします。',
        '$.pay_request',
        '{company_name}\nご担当者様\n\nいつもお世話になっております。\n\n請求書を添付にて送付いたします。\n内容をご確認のうえ、ご査収くださいますようお願いいたします。\n\nご不明点や修正がございましたら、お知らせください。\n何卒よろしくお願いいたします。'
    ),
    updated_by = 1,
    updated_at = '2026-05-26 00:00:00',
    deleted_at = NULL
WHERE name = 'mail-template'
  AND deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS mail_send_tasks
(
    id                  BIGINT        NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '发送任务ID',

    to_email            VARCHAR(320)  NOT NULL COMMENT '收件邮箱',
    cc                  VARCHAR(1024) NOT NULL DEFAULT '' COMMENT '抄送',
    subject             VARCHAR(512)  NOT NULL DEFAULT '' COMMENT '邮件主题',
    body                LONGTEXT      NOT NULL COMMENT '最终邮件正文',
    attachments         JSON          NOT NULL COMMENT '附件存储引用列表',
    mail_type           INT           NOT NULL DEFAULT -1 COMMENT '邮件类型 0:bp 1:技术者送信 2:案件送信 3:发注 4:请求书 -1:其他',

    company_name        VARCHAR(255)  NOT NULL DEFAULT '' COMMENT '公司名快照',
    contact_name        VARCHAR(255)  NOT NULL DEFAULT '' COMMENT '联系人名快照',
    error_message       TEXT          NULL COMMENT '邮件发送错误信息',

    created_by          BIGINT        NOT NULL COMMENT '创建员工ID',
    created_at          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COMMENT = '邮件发送任务队列表';
