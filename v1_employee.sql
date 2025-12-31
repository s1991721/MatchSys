CREATE TABLE user_login
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


CREATE TABLE employee
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

CREATE TABLE technician
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
