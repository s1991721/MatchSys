CREATE TABLE `sent_email_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',

  `message_id` VARCHAR(255) NOT NULL COMMENT 'Gmail Message-ID',
  `to` VARCHAR(512) NOT NULL DEFAULT '' COMMENT '收件人',
  `cc` VARCHAR(512) NOT NULL DEFAULT '' COMMENT '抄送',
  `subject` VARCHAR(512) NOT NULL DEFAULT '' COMMENT '邮件主题',
  `body` TEXT NOT NULL COMMENT '邮件正文',
  `attachments` TEXT NOT NULL COMMENT '附件列表(JSON字符串)',

  `status` VARCHAR(20) NOT NULL DEFAULT 'sent' COMMENT '发送状态',
  `sent_at` DATETIME NOT NULL COMMENT '邮件发送时间',

  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_message_id` (`message_id`),
  KEY `idx_status` (`status`),
  KEY `idx_sent_at` (`sent_at`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='已发送邮件日志(Gmail API)';
