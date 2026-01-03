CREATE TABLE mail_project_info
(
    id      VARCHAR(255) PRIMARY KEY,
    title   VARCHAR(255) NOT NULL COMMENT '邮件标题',
    address VARCHAR(255) NOT NULL COMMENT '发件人',
    body    TEXT COMMENT '正文内容',
    files   TEXT COMMENT '附件信息',
    date    DATETIME COMMENT '日期',
    remark  VARCHAR(500) COMMENT '备注',
    country VARCHAR(100) COMMENT '国家',
    skills  VARCHAR(255) COMMENT '技能要求',
    price   DECIMAL(10, 2) COMMENT '价格'
) COMMENT ='邮件案件表';


CREATE TABLE mail_technician_info
(
    id      VARCHAR(255) PRIMARY KEY,
    title   VARCHAR(255) NOT NULL COMMENT '邮件标题',
    address VARCHAR(255) NOT NULL COMMENT '发件人',
    body    TEXT COMMENT '正文内容',
    files   TEXT COMMENT '附件信息',
    date    DATETIME COMMENT '日期',
    remark  VARCHAR(500) COMMENT '备注',
    country VARCHAR(100) COMMENT '国家',
    skills  VARCHAR(255) COMMENT '技能要求',
    price   DECIMAL(10, 2) COMMENT '价格'
) COMMENT ='邮件技术者表';


CREATE TABLE saved_mail_info
(
    id   VARCHAR(255) PRIMARY KEY,
    date DATETIME COMMENT '日期'

) COMMENT ='系统中存储的邮件列表';