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

    wrong_label     TINYINT(1)    COMMENT '错误分类',
    correct_label   TINYINT(1)    COMMENT '正确分类'
)
COMMENT = '错误邮件记录表';