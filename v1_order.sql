CREATE TABLE purchase_order (
    id              BIGINT  NOT NULL AUTO_INCREMENT COMMENT '主键',
    order_no        VARCHAR(50) NOT NULL COMMENT '发注单号',
    person_in_charge VARCHAR(100) NOT NULL COMMENT '负责人',
    status          VARCHAR(50) NOT NULL COMMENT '状态',
    project_name    VARCHAR(255) NOT NULL COMMENT '项目名称',
    customer_id     BIGINT  NOT NULL COMMENT '客户ID',
    customer_name   VARCHAR(255) NOT NULL COMMENT '客户名称',
    technician_name VARCHAR(255) COMMENT '技术人员名称',
    price           DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '金额',
    working_hours   DECIMAL(8,2) DEFAULT 0 COMMENT '工时',
    period_start DATE NOT NULL COMMENT '期间开始日',
    period_end   DATE NOT NULL COMMENT '期间结束日',

    created_by      VARCHAR(100) NOT NULL COMMENT '创建人',
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by      VARCHAR(100) COMMENT '更新人',
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at      DATETIME NULL COMMENT '删除时间（逻辑删除）',
    PRIMARY KEY (id),
    UNIQUE KEY uk_purchase_order_no (order_no),
    KEY idx_purchase_customer (customer_id),
    KEY idx_purchase_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='发注表';

CREATE TABLE sales_order (
    id              BIGINT  NOT NULL AUTO_INCREMENT COMMENT '主键',
    order_no        VARCHAR(50) NOT NULL COMMENT '受注单号',
    person_in_charge VARCHAR(100) NOT NULL COMMENT '负责人',
    status          VARCHAR(50) NOT NULL COMMENT '状态',
    purchase_id     BIGINT  NOT NULL COMMENT '对应发注ID',
    project_name    VARCHAR(255) NOT NULL COMMENT '项目名称',
    customer_id     BIGINT  NOT NULL COMMENT '客户ID',
    customer_name   VARCHAR(255) NOT NULL COMMENT '客户名称',
    technician_id   BIGINT  COMMENT '技术人员ID',
    technician_name VARCHAR(255) COMMENT '技术人员名称',
    price           DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '金额',
    working_hours   DECIMAL(8,2) DEFAULT 0 COMMENT '工时',
    period_start DATE NOT NULL COMMENT '期间开始日',
    period_end   DATE NOT NULL COMMENT '期间结束日',
    created_by      VARCHAR(100) NOT NULL COMMENT '创建人',
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_by      VARCHAR(100) COMMENT '更新人',
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted_at      DATETIME NULL COMMENT '删除时间（逻辑删除）',
    PRIMARY KEY (id),
    UNIQUE KEY uk_sales_order_no (order_no),
    KEY idx_sales_purchase (purchase_id),
    KEY idx_sales_customer (customer_id),
    KEY idx_sales_status (status),
    CONSTRAINT fk_sales_purchase
        FOREIGN KEY (purchase_id)
        REFERENCES purchase_order (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='受注表';
