ALTER TABLE customer
    ADD COLUMN payment_info JSON DEFAULT NULL COMMENT '支付信息' AFTER remark;

ALTER TABLE employee
    ADD COLUMN bank_info JSON DEFAULT NULL COMMENT '员工银行信息' AFTER seal;

INSERT INTO sys_menu (menu_name, menu_html, sort_order)
VALUES ('财务管理', 'finance.html', 17);

INSERT INTO sys_role (id, role_name, description, menu_list)
VALUES (3, '财务', '公司财务部成员', '[finance.html]');

CREATE TABLE IF NOT EXISTS payroll_basic_info
(
    id                    BIGINT         NOT NULL PRIMARY KEY AUTO_INCREMENT,

    employee_id           BIGINT         NOT NULL COMMENT '员工ID',
    employee_name         VARCHAR(100)   NOT NULL COMMENT '员工姓名',
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

CREATE TABLE IF NOT EXISTS payroll_monthly_calculation
(
    id                      BIGINT         NOT NULL PRIMARY KEY AUTO_INCREMENT,

    payroll_month           DATE           NOT NULL COMMENT '工资月份，固定使用当月1日，例如 2026-05-01',

    employee_id             BIGINT         NOT NULL COMMENT '员工ID',
    employee_name           VARCHAR(100)   NOT NULL COMMENT '员工姓名',
    contract_type           TINYINT        NOT NULL DEFAULT 0 COMMENT '契约类型：0-正社员 1-契约社员 2-フリーランス',

    attendance_days         DECIMAL(5, 2)  NOT NULL DEFAULT 0 COMMENT '出勤日数，允许小数',

    base_salary             DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '基本工资',
    allowance_amount        DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '补贴',
    deduction_amount        DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '扣款',
    social_insurance_amount DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '社保/年金/保险',
    net_salary              DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '实发金额',

    bank_info               JSON           NULL COMMENT '员工银行信息快照，用于工资导出',

    status                  TINYINT        NOT NULL DEFAULT 0 COMMENT '状态：0-未确认 1-已确认 2-已发放',

    remark                  TEXT           NULL COMMENT '备注',

    created_by              BIGINT         NULL COMMENT '创建人 employee.id',
    created_at              DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by              BIGINT         NULL COMMENT '更新人 employee.id',
    updated_at              DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at              DATETIME       NULL COMMENT '删除时间（软删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT = '月度工资计算表';

CREATE TABLE IF NOT EXISTS finance_receivable
(
    id                 BIGINT         NOT NULL PRIMARY KEY AUTO_INCREMENT,

    pay_request_id     BIGINT         NULL COMMENT '来源请求书 pay_request.id',
    request_no         VARCHAR(50)    NULL COMMENT '请求书号快照',

    customer_id        BIGINT         NULL COMMENT '客户ID',
    customer_name      VARCHAR(255)   NOT NULL COMMENT '客户名称快照',

    receivable_amount  DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '应收金额',
    received_amount    DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '已收金额',
    outstanding_amount DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '未收金额',

    due_date           DATE           NULL COMMENT '预定到账日/入金期日',

    finance_status     TINYINT        NOT NULL DEFAULT 0 COMMENT '财务处理状态：0-正常 1-异常 2-核销',

    remark             TEXT           NULL COMMENT '备注',

    created_by         BIGINT         NULL COMMENT '创建人 employee.id',
    created_at         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by         BIGINT         NULL COMMENT '更新人 employee.id',
    updated_at         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at         DATETIME       NULL COMMENT '删除时间（软删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT = '应收台账表';

CREATE TABLE IF NOT EXISTS finance_receipt
(
    id             BIGINT         NOT NULL PRIMARY KEY AUTO_INCREMENT,

    receivable_id  BIGINT         NOT NULL COMMENT '应收台账 finance_receivable.id',

    customer_id    BIGINT         NULL COMMENT '客户ID，可为空',
    payer_name     VARCHAR(255)   NULL COMMENT '付款方名称/银行流水付款人',
    bank_transaction_no VARCHAR(100) NULL COMMENT '银行流水号/交易编号',

    receipt_amount DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '入金金额',
    receipt_date   DATE           NOT NULL COMMENT '入金日',

    remark         TEXT           NULL COMMENT '备注',

    created_by     BIGINT         NULL COMMENT '创建人 employee.id',
    created_at     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by     BIGINT         NULL COMMENT '更新人 employee.id',
    updated_at     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at     DATETIME       NULL COMMENT '删除时间（软删除）'

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT = '入金/收款记录表';
