-- Django server-side session storage.
-- This project manages schema changes with versioned SQL, so only the runtime
-- session table is created; django_migrations is intentionally not required.
CREATE TABLE IF NOT EXISTS django_session
(
    session_key  VARCHAR(40) NOT NULL PRIMARY KEY,
    session_data LONGTEXT    NOT NULL,
    expire_date  DATETIME(6) NOT NULL,

    INDEX django_session_expire_date_a5c62663 (expire_date)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COMMENT = 'Django server-side sessions';

INSERT INTO sys_menu (id, menu_name, menu_html, sort_order)
VALUES (4, '案件展示', 'case_exhibition_admin.html', 4);
