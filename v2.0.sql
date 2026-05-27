ALTER TABLE customer
    ADD COLUMN payment_info JSON DEFAULT NULL COMMENT '支付信息' AFTER remark;

INSERT INTO sys_menu (menu_name, menu_html, sort_order)
VALUES ('财务管理', 'finance.html', 17);
