ALTER TABLE customer
    ADD COLUMN payment_info JSON DEFAULT NULL COMMENT '支付信息' AFTER remark;

INSERT INTO sys_menu (menu_name, menu_html, sort_order)
VALUES ('财务管理', 'finance.html', 17);

INSERT INTO sys_role (id, role_name, description, menu_list)
VALUES (3, '财务', '公司财务部成员', '[finance.html]');

CREATE TABLE IF NOT EXISTS payroll_basic_info
(
    id                    BIGINT         NOT NULL PRIMARY KEY AUTO_INCREMENT,

    employee_id           BIGINT         NOT NULL COMMENT '员工ID',
    contract_type         TINYINT        NOT NULL DEFAULT 0 COMMENT '契约类型：0-正社员 1-契约社员 2-フリーランス',

    base_salary           DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '基本工资',
    health_insurance      DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '社保/健康保险',
    welfare_pension       DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '厚生年金',
    employment_insurance  DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '雇用保险',
    income_tax            DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '所得税',

    valid_until_date      DATE           NULL COMMENT '有效期截止日',
    status                TINYINT        NOT NULL DEFAULT 1 COMMENT '状态：1-有效 0-无效',

    remark                TEXT           NULL COMMENT '备注',

    created_by            BIGINT         NULL COMMENT '创建人 employee.id',
    created_at            DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by            BIGINT         NULL COMMENT '更新人 employee.id',
    updated_at            DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at            DATETIME       NULL COMMENT '删除时间（软删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT = '工资基础信息表';
