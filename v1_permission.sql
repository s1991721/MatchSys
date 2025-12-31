CREATE TABLE `sys_menu`
(
    `id`         BIGINT       NOT NULL AUTO_INCREMENT,
    `menu_name`  VARCHAR(100) NOT NULL,
    `menu_html`  VARCHAR(200) NOT NULL,
    `sort_order` INT          NOT NULL DEFAULT 0,
    `created_by` VARCHAR(64)  NULL,
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_by` VARCHAR(64)  NULL,
    `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `deleted_at` DATETIME     NULL,
    PRIMARY KEY (`id`)
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


CREATE TABLE `sys_role`
(
    `id`          BIGINT       NOT NULL AUTO_INCREMENT,
    `role_name`   VARCHAR(100) NOT NULL,
    `description` TEXT         NULL,
    `menu_list`   TEXT         NULL,
    `created_by`  VARCHAR(64)  NULL,
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_by`  VARCHAR(64)  NULL,
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `deleted_at`  DATETIME     NULL,
    PRIMARY KEY (`id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4;

INSERT INTO sys_role (id,role_name, description, menu_list)
VALUES (1,'技术者', '公司内技术人员', '[myattendance.html]'),
       (2,'营业', '公司营业部成员','[home.html,match.html,qiuanjian.html,songxinhistory.html,people.html,attendance.html,myattendance.html,order.html,pay_request.html]'),
       (999,'管理员', '整个系统的管理者', '*');
