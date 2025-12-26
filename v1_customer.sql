CREATE TABLE customer (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',

    company_name VARCHAR(255) NOT NULL COMMENT '公司名称',
    company_address VARCHAR(500) DEFAULT NULL COMMENT '公司地址',

    contract TEXT DEFAULT NULL COMMENT '合同信息',
    remark TEXT DEFAULT NULL COMMENT '备注',

    contact1_name VARCHAR(100) DEFAULT NULL COMMENT '联系人1姓名',
    contact1_position VARCHAR(100) DEFAULT NULL COMMENT '联系人1职位',
    contact1_email VARCHAR(255) DEFAULT NULL COMMENT '联系人1邮箱',
    contact1_phone VARCHAR(50) DEFAULT NULL COMMENT '联系人1电话',

    contact2_name VARCHAR(100) DEFAULT NULL COMMENT '联系人2姓名',
    contact2_position VARCHAR(100) DEFAULT NULL COMMENT '联系人2职位',
    contact2_email VARCHAR(255) DEFAULT NULL COMMENT '联系人2邮箱',
    contact2_phone VARCHAR(50) DEFAULT NULL COMMENT '联系人2电话',

    contact3_name VARCHAR(100) DEFAULT NULL COMMENT '联系人3姓名',
    contact3_position VARCHAR(100) DEFAULT NULL COMMENT '联系人3职位',
    contact3_email VARCHAR(255) DEFAULT NULL COMMENT '联系人3邮箱',
    contact3_phone VARCHAR(50) DEFAULT NULL COMMENT '联系人3电话',

    person_in_charge VARCHAR(100) DEFAULT NULL COMMENT '负责人',

    created_by BIGINT UNSIGNED DEFAULT NULL COMMENT '创建人',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    updated_by BIGINT UNSIGNED DEFAULT NULL COMMENT '更新人',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    deleted_at DATETIME DEFAULT NULL COMMENT '删除时间（逻辑删除）',

    PRIMARY KEY (id),

    INDEX idx_company_name (company_name),
    INDEX idx_person_in_charge (person_in_charge),
    INDEX idx_deleted_at (deleted_at)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='客户主表';
