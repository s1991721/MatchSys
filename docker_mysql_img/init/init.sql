/*!40101 SET NAMES utf8mb4 */;
SET character_set_client = utf8mb4;
SET character_set_connection = utf8mb4;
SET character_set_results = utf8mb4;

-- 创建业务数据库
CREATE DATABASE IF NOT EXISTS matchSys DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE matchSys;

-- 创建业务用户（只允许远程连接）
CREATE USER IF NOT EXISTS 'bpmatch_user'@'%'
  IDENTIFIED BY 'bpmatch_user_AbCdEfG';

-- 授权
GRANT ALL PRIVILEGES ON matchSys.* TO 'bpmatch_user'@'%';

FLUSH PRIVILEGES;

# ----------------------------------------------- 登录及权限 -----------------------------------------------
CREATE TABLE IF NOT EXISTS user_login
(
    employee_id         BIGINT       NOT NULL PRIMARY KEY COMMENT '员工ID，对应 employee.id',
    employee_name       VARCHAR(100) NOT NULL COMMENT '员工姓名',

    user_name           VARCHAR(100) NOT NULL COMMENT '登录用户名',
    password            VARCHAR(255) NOT NULL COMMENT '密码（建议存 hash）',
    password_expires_at DATETIME     NULL COMMENT '密码过期时间',

    role_id             BIGINT       NULL COMMENT '角色id',
    menu_list           TEXT         NULL COMMENT '拥有的菜单',

    created_by          BIGINT       NULL COMMENT '创建人 employee.id',
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by          BIGINT       NULL COMMENT '更新人 employee.id',
    updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at          DATETIME     NULL COMMENT '删除时间（软删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='用户登录表';


INSERT INTO user_login (employee_id, employee_name, user_name, password, role_id, menu_list, created_by, created_at,
                        updated_by, updated_at, deleted_at)
VALUES (1, '系统管理员', 'admin', 'admin',
        999, '["*"]', NULL, NOW(), NULL, NOW(), NULL);


CREATE TABLE IF NOT EXISTS login_audit
(
    id          BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    employee_id BIGINT       NULL COMMENT '员工ID',
    user_name   VARCHAR(100) NOT NULL DEFAULT '' COMMENT '登录账号',
    success     TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否成功',
    reason      VARCHAR(255) NULL COMMENT '失败原因',
    ip_address  VARCHAR(45)  NULL COMMENT 'IP地址',
    user_agent  VARCHAR(512) NULL COMMENT 'User-Agent',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_login_audit_employee_id (employee_id),
    INDEX idx_login_audit_created_at (created_at)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='登录日志';


CREATE TABLE IF NOT EXISTS sys_menu
(
    id         BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    menu_name  VARCHAR(100) NOT NULL COMMENT '菜单名',
    menu_html  VARCHAR(200) NOT NULL COMMENT '菜单对应html',
    sort_order INT          NOT NULL DEFAULT 0 COMMENT '排序',

    created_by BIGINT       NULL COMMENT '创建人 employee.id',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by BIGINT       NULL COMMENT '更新人 employee.id',
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at DATETIME     NULL COMMENT '删除时间（软删除）'
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;


INSERT INTO sys_menu (menu_name, menu_html, sort_order)
VALUES ('主页', 'home.html', 1),
       ('BP Match', 'bpmatch.html', 2),
       ('社内 Match', 'match.html', 3),
       ('送信历史', 'songxinhistory.html', 4),
       ('技术者管理', 'people.html', 5),
       ('社内人员管理', 'personnel.html', 6),
       ('考勤管理', 'attendance.html', 7),
       ('我的考勤', 'myattendance.html', 8),
       ('通知管理', 'notification.html', 9),
       ('注文书管理', 'order.html', 10),
       ('请求书管理', 'pay_request.html', 11),
       ('权限管理', 'permission.html', 12),
       ('登录日志', 'login_audit.html', 13),
       ('客户管理', 'customer.html', 14),
       ('数据分析', 'analysis.html', 15),
       ('系统设置', 'system_settings.html', 16),
       ('财务管理', 'finance.html', 17);


CREATE TABLE IF NOT EXISTS sys_role
(
    id          BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    role_name   VARCHAR(100) NOT NULL COMMENT '角色名',
    description TEXT         NULL COMMENT '描述',
    menu_list   TEXT         NULL COMMENT '对应菜单列表',

    created_by  BIGINT       NULL COMMENT '创建人 employee.id',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by  BIGINT       NULL COMMENT '更新人 employee.id',
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at  DATETIME     NULL COMMENT '删除时间（软删除）'
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

INSERT INTO sys_role (id, role_name, description, menu_list)
VALUES (1, '技术者', '公司内技术人员', '[myattendance.html]'),
       (2, '营业', '公司营业部成员',
        '[home.html,bpmatch.html,match.html,songxinhistory.html,people.html,attendance.html,myattendance.html,order.html,pay_request.html]'),
       (999, '管理员', '整个系统的管理者', '*');


# ----------------------------------------------- 员工及技术者 -----------------------------------------------
CREATE TABLE IF NOT EXISTS employee
(
    id                             BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '员工ID',

    name                           VARCHAR(100) NOT NULL COMMENT '姓名',
    gender                         TINYINT      NULL COMMENT '性别：0未知 / 1男 / 2女',
    birthday                       DATE         NULL COMMENT '出生日期',

    phone                          VARCHAR(20)  NULL COMMENT '手机号',
    email                          VARCHAR(255) NULL COMMENT '邮箱',
    address                        VARCHAR(255) NULL COMMENT '家庭住址',

    emergency_contact_name         VARCHAR(100) NULL COMMENT '紧急联系人姓名',
    emergency_contact_phone        VARCHAR(20)  NULL COMMENT '紧急联系人电话',
    emergency_contact_relationship VARCHAR(50)  NULL COMMENT '紧急联系人关系',

    hire_date                      DATE         NULL COMMENT '入职日期',
    leave_date                     DATE         NULL COMMENT '离职日期',

    department_name                VARCHAR(100) NULL COMMENT '部门名称',
    position_name                  VARCHAR(100) NULL COMMENT '职位名称',

    status                         SMALLINT     NULL COMMENT '1在职/0离职/2停用...',
    seal                           VARCHAR(255) NULL COMMENT '个人印章文件路径',

    created_by                     BIGINT       NULL COMMENT '创建人 employee.id',
    created_at                     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by                     BIGINT       NULL COMMENT '更新人 employee.id',
    updated_at                     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at                     DATETIME     NULL COMMENT '删除时间（软删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='员工表';

INSERT INTO employee (id, name, department_name, position_name)
VALUES (1, '系统管理员', '系统管理', '管理员');


CREATE TABLE IF NOT EXISTS technician
(
    employee_id            BIGINT         NOT NULL PRIMARY KEY COMMENT '员工ID',

    name                   VARCHAR(100)   NOT NULL COMMENT '姓名',
    name_mask              VARCHAR(100)   NOT NULL COMMENT '姓名掩码',
    birthday               DATE           NULL COMMENT '生日',

    nationality            TINYINT        NULL COMMENT '国籍：0-日本 1-其他',
    price                  DECIMAL(12, 2) NULL COMMENT '单价/报价',
    introduction           TEXT           NULL COMMENT '简介',

    contract_type          TINYINT        NOT NULL DEFAULT 0 COMMENT '合同类型：0-正社员 1-契约社员 2-フリーランス ',
    spot_contract_deadline DATE           NULL COMMENT '现场合同截止日',
    business_status        TINYINT        NOT NULL DEFAULT 0 COMMENT '营业状态：(0, "营业中"),(1, "营业中1/2等待"),(2, "营业中结果等待"),(3, "现场中"),(4, "现场已确定"), ',
    ss                     VARCHAR(100)   NULL COMMENT 'ss文件路径',

    remark                 TEXT           NULL COMMENT '备注',

    created_by             BIGINT         NULL COMMENT '创建人 employee.id',
    created_at             DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by             BIGINT         NULL COMMENT '更新人 employee.id',
    updated_at             DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at             DATETIME       NULL COMMENT '删除时间（软删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='技术人员表';


# ----------------------------------------------- 考勤 -----------------------------------------------
CREATE TABLE IF NOT EXISTS attendance_policy
(
    id              BIGINT         NOT NULL PRIMARY KEY AUTO_INCREMENT,
    employee_id     BIGINT         NOT NULL COMMENT '员工ID',
    annual_leave    INT            NULL COMMENT '剩余年假',

    work_start_time TIME           NOT NULL COMMENT '上班时间',
    work_end_time   TIME           NOT NULL COMMENT '下班时间',

    location_name   VARCHAR(100)   NOT NULL COMMENT '工作地信息',
    latitude        DECIMAL(10, 7) NOT NULL COMMENT '工作地纬度',
    longitude       DECIMAL(10, 7) NOT NULL COMMENT '工作地经度',
    radius_meters   INT            NOT NULL DEFAULT 200 COMMENT '工作地中心半径',

    remark          VARCHAR(255)   NULL COMMENT '备注',

    created_by      BIGINT         NULL COMMENT '创建人 employee.id',
    created_at      DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by      BIGINT         NULL COMMENT '更新人 employee.id',
    updated_at      DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at      DATETIME       NULL COMMENT '删除时间（软删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='考勤规则';


INSERT INTO attendance_policy(employee_id, work_start_time, work_end_time, location_name, latitude, longitude,
                              radius_meters, remark, created_by, created_at, updated_by, updated_at, deleted_at)
VALUES (1, '09:00:00', '18:00:00', '公司总部',
        35.6894870, 139.6917060, 200, '系统默认考勤规则',
        1, NOW(), NULL, NOW(), NULL);


CREATE TABLE IF NOT EXISTS attendance_punch
(
    id            BIGINT         NOT NULL PRIMARY KEY AUTO_INCREMENT,
    employee_id   BIGINT         NOT NULL COMMENT '员工ID',

    punch_date    DATE           NOT NULL COMMENT '打卡日期',
    punch_time    TIME           NOT NULL COMMENT '打卡时间',
    punch_type    SMALLINT       NOT NULL COMMENT '打卡类型 #1上班 2下班',

    latitude      DECIMAL(10, 7) NULL COMMENT '打卡纬度',
    longitude     DECIMAL(10, 7) NULL COMMENT '打卡经度',
    location_text VARCHAR(255)   NULL COMMENT '打卡地信息',

    remark        VARCHAR(255)   NULL COMMENT '备注',

    created_by    BIGINT         NULL COMMENT '创建人 employee.id',
    created_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by    BIGINT         NULL COMMENT '更新人 employee.id',
    updated_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at    DATETIME       NULL COMMENT '删除时间（软删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='打卡表';


CREATE TABLE IF NOT EXISTS attendance_record
(
    id          BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
    employee_id BIGINT       NOT NULL COMMENT '员工ID',

    punch_date  DATE         NOT NULL COMMENT '考勤日期',
    start_time  TIME         NULL COMMENT '考勤上班时间',
    end_time    TIME         NULL COMMENT '考勤下班时间',

    remark      VARCHAR(255) NULL COMMENT '备注',

    created_by  BIGINT       NULL COMMENT '创建人 employee.id',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by  BIGINT       NULL COMMENT '更新人 employee.id',
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at  DATETIME     NULL COMMENT '删除时间（软删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='考勤表';


# ----------------------------------------------- 客户 -----------------------------------------------
CREATE TABLE IF NOT EXISTS customer
(
    id                BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',

    company_name      VARCHAR(255) NOT NULL COMMENT '公司名称',
    company_address   VARCHAR(500)          DEFAULT NULL COMMENT '公司地址',
    company_email    VARCHAR(255)          DEFAULT NULL COMMENT '公司邮箱',

    contract          TEXT                  DEFAULT NULL COMMENT '合同信息',
    remark            TEXT                  DEFAULT NULL COMMENT '备注',
    payment_info      JSON                  DEFAULT NULL COMMENT '支付信息',

    contact1_name     VARCHAR(100)          DEFAULT NULL COMMENT '联系人1姓名',
    contact1_position VARCHAR(100)          DEFAULT NULL COMMENT '联系人1职位',
    contact1_email    VARCHAR(255)          DEFAULT NULL COMMENT '联系人1邮箱',
    contact1_phone    VARCHAR(50)           DEFAULT NULL COMMENT '联系人1电话',

    contact2_name     VARCHAR(100)          DEFAULT NULL COMMENT '联系人2姓名',
    contact2_position VARCHAR(100)          DEFAULT NULL COMMENT '联系人2职位',
    contact2_email    VARCHAR(255)          DEFAULT NULL COMMENT '联系人2邮箱',
    contact2_phone    VARCHAR(50)           DEFAULT NULL COMMENT '联系人2电话',

    contact3_name     VARCHAR(100)          DEFAULT NULL COMMENT '联系人3姓名',
    contact3_position VARCHAR(100)          DEFAULT NULL COMMENT '联系人3职位',
    contact3_email    VARCHAR(255)          DEFAULT NULL COMMENT '联系人3邮箱',
    contact3_phone    VARCHAR(50)           DEFAULT NULL COMMENT '联系人3电话',

    person_in_charge  VARCHAR(100)          DEFAULT NULL COMMENT '负责人',

    created_by        BIGINT                DEFAULT NULL COMMENT '创建人',
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by        BIGINT                DEFAULT NULL COMMENT '更新人',
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at        DATETIME              DEFAULT NULL COMMENT '删除时间（逻辑删除）'


) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='客户主表';


# ----------------------------------------------- 注文 -----------------------------------------------
CREATE TABLE IF NOT EXISTS purchase_order
(
    id                  BIGINT         NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    order_no            VARCHAR(50)    NOT NULL COMMENT '发注单号',

    person_in_charge    VARCHAR(100)   NOT NULL COMMENT '负责人',
    person_in_charge_id BIGINT         NULL COMMENT '负责人id',

    work_content        VARCHAR(500)   NULL COMMENT '作業内容',
    work_place          VARCHAR(255)   NULL COMMENT '作業場所',
    contract_type       VARCHAR(100)   NULL COMMENT '契約形態',
    payment_terms       VARCHAR(255)   NULL COMMENT '支払い条件',

    status              VARCHAR(50)    NOT NULL COMMENT '状态',
    project_name        VARCHAR(255)   NOT NULL COMMENT '项目名称',
    customer_id         BIGINT         NOT NULL COMMENT '客户ID',
    customer_name       VARCHAR(255)   NOT NULL COMMENT '客户名称',

    line_items          JSON           NULL COMMENT '契约明细JSON',

    period_start        DATE           NOT NULL COMMENT '期间开始日',
    period_end          DATE           NOT NULL COMMENT '期间结束日',
    remark              TEXT           COMMENT '备注',
    pdf_file            VARCHAR(255)   NULL COMMENT '发注书PDF文件路径',

    created_by          VARCHAR(100)   NOT NULL COMMENT '创建人',
    created_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by          VARCHAR(100) COMMENT '更新人',
    updated_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at          DATETIME       NULL COMMENT '删除时间（逻辑删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='发注表';

CREATE TABLE IF NOT EXISTS sales_order
(
    id                  BIGINT         NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    order_no            VARCHAR(50)    NOT NULL COMMENT '受注单号',
    person_in_charge    VARCHAR(100)   NOT NULL COMMENT '负责人',
    person_in_charge_id BIGINT         NULL COMMENT '负责人id',
    status              VARCHAR(50)    NOT NULL COMMENT '状态',
    purchase_id         BIGINT         NULL COMMENT '对应发注ID（BP明细）',
    project_name        VARCHAR(255)   NOT NULL COMMENT '项目名称',
    customer_id         BIGINT         NOT NULL COMMENT '客户ID',
    customer_name       VARCHAR(255)   NOT NULL COMMENT '客户名称',
    technician_id       BIGINT         NULL COMMENT '技术人员ID（自社人员明细）',
    technician_name     VARCHAR(255)   NULL COMMENT '技术人员名称',
    price               DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '契约单价',
    line_items          JSON           NULL COMMENT '原始契约明细JSON',
    period_start        DATE           NOT NULL COMMENT '期间开始日',
    period_end          DATE           NOT NULL COMMENT '期间结束日',
    remark              TEXT COMMENT '备注',
    pdf_file            VARCHAR(255)   NULL COMMENT '受注书PDF文件路径',

    created_by          VARCHAR(100)   NOT NULL COMMENT '创建人',
    created_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by          VARCHAR(100) COMMENT '更新人',
    updated_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at          DATETIME       NULL COMMENT '删除时间（逻辑删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='受注表';

CREATE TABLE pay_request
(
    id            bigint         NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    request_no    varchar(50)    NOT NULL COMMENT '请求书编号',
    order_no      varchar(50)             DEFAULT NULL COMMENT '对应注文书编号',
    subject       varchar(255)            DEFAULT NULL COMMENT '件名',
    status        varchar(50)    NOT NULL COMMENT '状态：待付款 已付款 已取消',
    customer_id   bigint         NOT NULL COMMENT '客户ID',
    customer_name varchar(255)   NOT NULL COMMENT '客户名称',
    total_amount  decimal(12, 2) NOT NULL DEFAULT 0.00 COMMENT '总价',
    due_date      DATE                    DEFAULT NULL COMMENT '入金期日',
    details       TEXT                    DEFAULT NULL COMMENT '明细JSON',

    pdf_file      VARCHAR(255)            DEFAULT NULL COMMENT '请求书PDF文件路径',
    remark        TEXT                    DEFAULT NULL COMMENT '备注',

    created_by    VARCHAR(100)   NOT NULL COMMENT '创建人',
    created_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by    VARCHAR(100) COMMENT '更新人',
    updated_at    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at    DATETIME       NULL COMMENT '删除时间（逻辑删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='请求书';

# ----------------------------------------------- match -----------------------------------------------
CREATE TABLE IF NOT EXISTS sent_email_logs
(
    id          BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',

    message_id  VARCHAR(255) NOT NULL COMMENT 'Gmail Message-ID',
    `to`        VARCHAR(512) NOT NULL DEFAULT '' COMMENT '收件人',
    cc          VARCHAR(512) NOT NULL DEFAULT '' COMMENT '抄送',
    subject     VARCHAR(512) NOT NULL DEFAULT '' COMMENT '邮件主题',
    body        TEXT         NOT NULL COMMENT '邮件正文',
    attachments TEXT         NOT NULL COMMENT '附件列表(JSON字符串)',

    mail_type   INT          NOT NULL COMMENT '邮件类型 0:bp 1:技术者送信 2:案件送信 3:发注 4:请求书 -1:其他',
    sent_at     DATETIME     NOT NULL COMMENT '邮件发送时间',

    created_by  VARCHAR(100) NOT NULL COMMENT '创建人',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by  VARCHAR(100) COMMENT '更新人',
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at  DATETIME     NULL COMMENT '删除时间（逻辑删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='已发送邮件日志(Gmail API)';

CREATE TABLE IF NOT EXISTS mail_project_info
(
    id      VARCHAR(255) PRIMARY KEY,
    title   VARCHAR(500) NOT NULL COMMENT '邮件标题',
    address VARCHAR(255) NOT NULL COMMENT '发件人',
    body    TEXT COMMENT '正文内容',
    files   TEXT COMMENT '附件信息',
    date    DATETIME COMMENT '日期',
    remark  VARCHAR(500) COMMENT '备注',
    country VARCHAR(100) COMMENT '国家 0=日本籍 1=日本籍以外',
    skills  VARCHAR(500) COMMENT '技能要求',
    price   DECIMAL(12, 2) COMMENT '价格'
) COMMENT ='邮件案件表';

CREATE TABLE IF NOT EXISTS mail_technician_info
(
    id      VARCHAR(255) PRIMARY KEY,
    title   VARCHAR(500) NOT NULL COMMENT '邮件标题',
    address VARCHAR(255) NOT NULL COMMENT '发件人',
    body    TEXT COMMENT '正文内容',
    files   TEXT COMMENT '附件信息',
    date    DATETIME COMMENT '日期',
    remark  VARCHAR(500) COMMENT '备注',
    country VARCHAR(100) COMMENT '国家',
    skills  VARCHAR(500) COMMENT '技能要求',
    price   DECIMAL(12, 2) COMMENT '价格'
) COMMENT ='邮件技术者表';

CREATE TABLE IF NOT EXISTS saved_mail_info
(
    id   VARCHAR(255) PRIMARY KEY,
    date DATETIME COMMENT '日期'

) COMMENT ='系统中存储的邮件列表';

CREATE TABLE IF NOT EXISTS my_mail
(
    id               VARCHAR(255) NOT NULL COMMENT '外部邮件唯一标识（如 IMAP UID / Message-ID）',
    owner_id         BIGINT       NULL COMMENT '员工ID，对应 employee.id',
    subject          VARCHAR(512) NULL COMMENT '邮件主题',
    from_email       VARCHAR(255) NULL COMMENT '发件人',
    body             TEXT              COMMENT '正文内容',
    files            TEXT              COMMENT '附件信息',
    received_at      DATETIME     NULL COMMENT '接收时间',
    is_unread        TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否未读',

    PRIMARY KEY (id)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='我的邮件缓存表';

# ----------------------------------------------- 错误邮件 -----------------------------------------------
CREATE TABLE IF NOT EXISTS wrong_mail_info
(
    id            VARCHAR(255) PRIMARY KEY,
    title         VARCHAR(500) COMMENT '邮件标题',
    address       VARCHAR(255) NOT NULL COMMENT '发件人',
    body          TEXT COMMENT '正文内容',
    files         TEXT COMMENT '附件信息',
    date          DATETIME COMMENT '日期',
    remark        VARCHAR(500) COMMENT '备注',
    country       VARCHAR(100) COMMENT '国家 0=日本籍 1=日本籍以外',
    skills        VARCHAR(500) COMMENT '技能要求',
    price         DECIMAL(10, 2) COMMENT '价格',

    wrong_type    TINYINT(1) COMMENT '错误类型 1=邮件分类错误 2=国籍识别错误 3=关键词识别错误',
    wrong_label   TINYINT(1) COMMENT '错误分类',
    correct_label TINYINT(1) COMMENT '正确分类',
    deleted_at    DATETIME COMMENT '下载标记时间（软删除）'
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='错误邮件记录表';

# ----------------------------------------------- 系统设置 -----------------------------------------------

CREATE TABLE IF NOT EXISTS sys_settings
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
VALUES (
    'match',
    JSON_OBJECT(
        'cycle_days', 14
    ),
    1,
    '2026-01-03 17:08:42',
    1,
    '2026-01-04 14:01:59',
    NULL
);

INSERT INTO sys_settings (name, settings, created_by, created_at, updated_by, updated_at, deleted_at)
VALUES (
    'ai',
    JSON_OBJECT(
        'api_key', '',
        'mode_type', 'local',
        'model_name', 'llama3.2:3b-instruct-q4_K_M'
    ),
    1,
    '2026-01-04 05:31:02',
    1,
    '2026-01-04 05:42:31',
    NULL
);

INSERT INTO sys_settings (name, settings, created_by, created_at, updated_by, updated_at, deleted_at)
VALUES (
    'mail-template',
    JSON_OBJECT(
        'anjian',
        CONCAT(
            'いつもお世話になっております。\n',
            '株式会社の林でございます。\n\n',
            '技術者をご紹介いただきありがとうございます。\n',
            '弊社にて対応可能な案件をご紹介させて頂きます。\n',
            'ご検討頂けますと幸いです。\n\n',
            '**************************************\n',
            '{project_block}\n',
            '{detail_block}\n',
            '{requirement_block}\n',
            '{skills_must_block}\n',
            '{skills_can_block}\n',
            '{remark_block}\n',
            '**************************************\n\n',
            '今後とも何卒よろしくお願い申し上げます。\n\n',
            '＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝\n',
            '株式会社\n',
            '営業部　マネージャー：\n',
            '個人mail:gmail@outlook.com\n',
            '営業共通mail: outlook@gmail.com\n',
            'mobile: 010-2345-6789\n',
            '〒123-4567\n',
            '東京都XXX区XX町X丁目12-3\n',
            '第一 ビル 88F\n',
            'HP:https://www.homapage.jp/\n'
        ),
        'technician',
        CONCAT(
            'いつもお世話になっております。\n',
            '株式会社の林でございます。\n\n',
            '技術者をご紹介させて頂きます。\n',
            'ご検討頂けますと幸いです。\n\n',
            '**************************************\n',
            '{person_intro}\n',
            '**************************************\n\n',
            '今後とも何卒よろしくお願い申し上げます。\n\n',
            '＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝\n',
            '株式会社\n',
            '営業部　マネージャー：\n',
            '個人mail:gmail@outlook.com\n',
            '営業共通mail: outlook@gmail.com\n',
            'mobile: 010-2345-6789\n',
            '〒123-4567\n',
            '東京都XXX区XX町X丁目12-3\n',
            '第一 ビル 88F\n',
            'HP:https://www.homapage.jp/\n'
        ),
        'order',
        CONCAT(
            '{company_name}\n',
            'ご担当者様\n\n',
            'いつもお世話になっております。\n\n',
            '注文書を添付にて送付いたします。\n',
            '内容をご確認のうえ、ご査収くださいますようお願いいたします。\n\n',
            'ご不明点や修正がございましたら、お知らせください。\n',
            '何卒よろしくお願いいたします。'
        ),
        'pay_request',
        CONCAT(
            '{company_name}\n',
            'ご担当者様\n\n',
            'いつもお世話になっております。\n\n',
            '請求書を添付にて送付いたします。\n',
            '内容をご確認のうえ、ご査収くださいますようお願いいたします。\n\n',
            'ご不明点や修正がございましたら、お知らせください。\n',
            '何卒よろしくお願いいたします。'
        )
    ),
    1,
    '2026-04-22 15:10:29',
    1,
    '2026-05-26 00:00:00',
    NULL
);

CREATE TABLE IF NOT EXISTS sys_tasks
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

INSERT INTO sys_tasks (name,`time`,frequency,cron_expr,`method`,api,body,enabled,last_run_at,next_run_at,last_status,last_error,created_by,created_at,updated_by,updated_at,deleted_at) VALUES
	 ('夜间数据处理','01:00:00','每天','0 1 * * *','POST','/api/time-to-save','',1,'2026-02-13 16:00:00',NULL,'error','HTTP 403',1,'2026-01-04 14:51:21',1,'2026-02-13 16:00:00',NULL),
	 ('夜间过期数据清理','05:00:00','每天','0 5 * * *','POST','/api/time-to-clean','',1,'2026-01-10 20:00:00',NULL,'error','HTTP 500',1,'2026-01-04 15:20:48',1,'2026-01-10 20:00:00',NULL),
	 ('重要数据备份','01:00:00','每周','0 1 * * 6','POST','/api/time-to-backup','',1,'2026-02-13 16:00:00',NULL,'error','HTTP 403',1,'2026-01-04 15:21:50',1,'2026-02-13 16:00:00',NULL),
	 ('我的邮件定时同步','09:00:00','自定义 Cron','*/10 9-20 * * *','POST','/api/time-to-sync-my-mails','',1,'2026-02-13 16:00:00',NULL,'error','HTTP 403',1,'2026-01-04 15:21:50',1,'2026-02-13 16:00:00',NULL),
	 ('工作日日间数据处理','09:00:00','自定义 Cron','0 9-20 * * 1-5','POST','/api/time-to-save-day','',1,'2026-02-13 16:00:00',NULL,'error','HTTP 403',1,'2026-01-04 15:21:50',1,'2026-02-13 16:00:00',NULL);
