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


INSERT INTO sys_settings (name, settings, created_by, created_at, updated_by, updated_at, deleted_at) VALUES
       ('mail-template',
        '{"anjian": "いつもお世話になっております。\n株式会社の林でございます。\n\n技術者をご紹介いただきありがとうございます。\n弊社にて対応可能な案件をご紹介させて頂きます。\nご検討頂けますと幸いです。\n\n**************************************\n{project_block}\n{detail_block}\n{requirement_block}\n{skills_must_block}\n{skills_can_block}\n{remark_block}\n**************************************\n\n今後とも何卒よろしくお願い申し上げます。\n\n＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝\n株式会社\n営業部　マネージャー：\n個人mail:gmail@outlook.com\n営業共通mail: outlook@gmail.com\nmobile: 010-2345-6789\n〒123-4567\n東京都XXX区XX町X丁目12-3\n第一 ビル 88F\nHP:https://www.homapage.jp/\n"}',
        1, '2026-01-04 05:31:02', 1, '2026-01-04 05:31:02', NULL);