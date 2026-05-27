ALTER TABLE customer
    ADD COLUMN payment_info JSON DEFAULT NULL COMMENT '支付信息' AFTER remark;
