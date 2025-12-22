CREATE TABLE user_login (
    employee_id BIGINT NOT NULL COMMENT '员工ID，对应 employee.id',

    user_name VARCHAR(100) NOT NULL COMMENT '登录用户名',
    password VARCHAR(255) NOT NULL COMMENT '密码（建议存 hash）',

    created_by BIGINT NULL COMMENT '创建人（employee_id）',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by BIGINT NULL COMMENT '更新人（employee_id）',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at DATETIME NULL COMMENT '删除时间（软删除）',

    -- 主键：确保一名员工只有一个账号
    CONSTRAINT pk_user_login PRIMARY KEY (employee_id),

    -- 唯一约束：用户名唯一
    CONSTRAINT uk_user_login_user_name UNIQUE (user_name),

    -- 外键约束
    CONSTRAINT fk_user_login_employee
        FOREIGN KEY (employee_id)
        REFERENCES employee (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='用户登录表';



CREATE TABLE employee (
id BIGINT NOT NULL AUTO_INCREMENT COMMENT '员工ID',

name VARCHAR(100) NOT NULL COMMENT '姓名',
gender TINYINT NULL COMMENT '性别：0未知 / 1男 / 2女',
birthday DATE NULL COMMENT '出生日期',

phone VARCHAR(20) NULL COMMENT '手机号',
email VARCHAR(255) NULL COMMENT '邮箱',

address VARCHAR(255) NULL COMMENT '家庭住址',

emergency_contact_name VARCHAR(100) NULL COMMENT '紧急联系人姓名',
emergency_contact_phone VARCHAR(20) NULL COMMENT '紧急联系人电话',
emergency_contact_relationship VARCHAR(50) NULL COMMENT '紧急联系人关系',

hire_date DATE NULL COMMENT '入职日期',
leave_date DATE NULL COMMENT '离职日期',

department_name VARCHAR(100) NULL COMMENT '部门名称',
position_name VARCHAR(100) NULL COMMENT '职位名称',

status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：1在职 / 0离职 / 2停用',

created_by BIGINT NULL COMMENT '创建人 employee.id',
created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

updated_by BIGINT NULL COMMENT '更新人 employee.id',
updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

deleted_at DATETIME NULL COMMENT '删除时间（软删除）',

PRIMARY KEY (id),

-- 常用索引（为 Django / 后台列表 / 查询优化）
KEY idx_employee_phone (phone),
KEY idx_employee_email (email),
KEY idx_employee_department_name (department_name),
KEY idx_employee_position_name (position_name),
KEY idx_employee_status (status),
KEY idx_employee_deleted_at (deleted_at)
) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COMMENT='员工表';

CREATE TABLE technician (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键',

    employee_id BIGINT NOT NULL COMMENT '员工ID',

    name VARCHAR(100) NOT NULL COMMENT '姓名',
    name_mask VARCHAR(100) NOT NULL COMMENT '姓名掩码',

    birthday DATE NULL COMMENT '生日',

    nationality VARCHAR(50) NULL COMMENT '国籍',

    price DECIMAL(10,2) NULL COMMENT '单价/报价',

    introduction TEXT NULL COMMENT '简介',

    contract_type TINYINT NOT NULL DEFAULT 0 COMMENT '合同类型：0-未定 1-长期 2-短期 3-现场',

    spot_contract_deadline DATE NULL COMMENT '现场合同截止日',

    business_status TINYINT NOT NULL DEFAULT 0 COMMENT '业务状态：0-待机 1-可用 2-忙碌 3-不可用',

    ss TINYINT NULL COMMENT '技能等级/状态标识',

    remark TEXT NULL COMMENT '备注',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY uk_technician_employee (employee_id)
) COMMENT='技术人员表';
