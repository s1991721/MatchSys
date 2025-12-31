# ----------------------------------------------- 登录及权限 -----------------------------------------------
CREATE TABLE IF NOT EXISTS user_login
(
    employee_id   BIGINT       NOT NULL PRIMARY KEY COMMENT '员工ID，对应 employee.id',
    employee_name VARCHAR(100) NOT NULL COMMENT '员工姓名',

    user_name     VARCHAR(100) NOT NULL COMMENT '登录用户名',
    password      VARCHAR(255) NOT NULL COMMENT '密码（建议存 hash）',

    role_id       BIGINT       NULL COMMENT '角色id',
    menu_list     TEXT         NULL COMMENT '拥有的菜单',

    created_by    BIGINT       NULL COMMENT '创建人 employee.id',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by    BIGINT       NULL COMMENT '更新人 employee.id',
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at    DATETIME     NULL COMMENT '删除时间（软删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='用户登录表';


INSERT INTO user_login (employee_id, employee_name, user_name, password, role_id, menu_list, created_by, created_at,
                        updated_by, updated_at, deleted_at)
VALUES (1, '系统管理员', 'admin', 'admin',
        999, '["*"]', NULL, NOW(), NULL, NOW(), NULL);


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
       ('BP Match', 'match.html', 2),
       ('社内 Match', 'qiuanjian.html', 3),
       ('送信历史', 'songxinhistory.html', 4),
       ('技术者管理', 'people.html', 5),
       ('社内人员管理', 'personnel.html', 6),
       ('考勤管理', 'attendance.html', 7),
       ('我的考勤', 'myattendance.html', 8),
       ('通知管理', 'notification.html', 9),
       ('注文书管理', 'order.html', 10),
       ('请求书管理', 'pay_request.html', 11),
       ('权限管理', 'permission.html', 12),
       ('客户管理', 'customer.html', 13),
       ('数据分析', 'analysis.html', 14);


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
        '[home.html,match.html,qiuanjian.html,songxinhistory.html,people.html,attendance.html,myattendance.html,order.html,pay_request.html]'),
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

    created_by                     BIGINT       NULL COMMENT '创建人 employee.id',
    created_at                     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by                     BIGINT       NULL COMMENT '更新人 employee.id',
    updated_at                     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at                     DATETIME     NULL COMMENT '删除时间（软删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='员工表';


CREATE TABLE IF NOT EXISTS technician
(
    employee_id            BIGINT         NOT NULL PRIMARY KEY COMMENT '员工ID',

    name                   VARCHAR(100)   NOT NULL COMMENT '姓名',
    name_mask              VARCHAR(100)   NOT NULL COMMENT '姓名掩码',
    birthday               DATE           NULL COMMENT '生日',

    nationality            VARCHAR(50)    NULL COMMENT '国籍',
    price                  DECIMAL(10, 2) NULL COMMENT '单价/报价',
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

    contract          TEXT                  DEFAULT NULL COMMENT '合同信息',
    remark            TEXT                  DEFAULT NULL COMMENT '备注',

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
    id               BIGINT         NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    order_no         VARCHAR(50)    NOT NULL COMMENT '发注单号',
    person_in_charge VARCHAR(100)   NOT NULL COMMENT '负责人',
    status           VARCHAR(50)    NOT NULL COMMENT '状态',
    project_name     VARCHAR(255)   NOT NULL COMMENT '项目名称',
    customer_id      BIGINT         NOT NULL COMMENT '客户ID',
    customer_name    VARCHAR(255)   NOT NULL COMMENT '客户名称',
    technician_name  VARCHAR(255) COMMENT '技术人员名称',
    price            DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '金额',
    working_hours    DECIMAL(8, 2)           DEFAULT 0 COMMENT '工时',
    period_start     DATE           NOT NULL COMMENT '期间开始日',
    period_end       DATE           NOT NULL COMMENT '期间结束日',

    created_by       VARCHAR(100)   NOT NULL COMMENT '创建人',
    created_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by       VARCHAR(100) COMMENT '更新人',
    updated_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at       DATETIME       NULL COMMENT '删除时间（逻辑删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='发注表';

CREATE TABLE IF NOT EXISTS sales_order
(
    id               BIGINT         NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    order_no         VARCHAR(50)    NOT NULL COMMENT '受注单号',
    person_in_charge VARCHAR(100)   NOT NULL COMMENT '负责人',
    status           VARCHAR(50)    NOT NULL COMMENT '状态',
    purchase_id      BIGINT         NOT NULL COMMENT '对应发注ID',
    project_name     VARCHAR(255)   NOT NULL COMMENT '项目名称',
    customer_id      BIGINT         NOT NULL COMMENT '客户ID',
    customer_name    VARCHAR(255)   NOT NULL COMMENT '客户名称',
    technician_id    BIGINT COMMENT '技术人员ID',
    technician_name  VARCHAR(255) COMMENT '技术人员名称',
    price            DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '金额',
    working_hours    DECIMAL(8, 2)           DEFAULT 0 COMMENT '工时',
    period_start     DATE           NOT NULL COMMENT '期间开始日',
    period_end       DATE           NOT NULL COMMENT '期间结束日',

    created_by       VARCHAR(100)   NOT NULL COMMENT '创建人',
    created_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by       VARCHAR(100) COMMENT '更新人',
    updated_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at       DATETIME       NULL COMMENT '删除时间（逻辑删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT ='受注表';


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

    status      VARCHAR(20)  NOT NULL DEFAULT 'sent' COMMENT '发送状态',
    sent_at     DATETIME     NOT NULL COMMENT '邮件发送时间',

    created_by  VARCHAR(100) NOT NULL COMMENT '创建人',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by  VARCHAR(100) COMMENT '更新人',
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at  DATETIME     NULL COMMENT '删除时间（逻辑删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='已发送邮件日志(Gmail API)';
