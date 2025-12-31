CREATE TABLE attendance_policy
(
    id              BIGINT         NOT NULL AUTO_INCREMENT,
    employee_id     BIGINT         NOT NULL,

    work_start_time TIME           NOT NULL,
    work_end_time   TIME           NOT NULL,

    location_name   VARCHAR(100)   NOT NULL,
    latitude        DECIMAL(10, 7) NOT NULL,
    longitude       DECIMAL(10, 7) NOT NULL,
    radius_meters   INT            NOT NULL DEFAULT 200,

    remark          VARCHAR(255)   NULL,

    created_by      BIGINT         NULL,
    created_at      DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by      BIGINT         NULL,
    updated_at      DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    deleted_at      DATETIME       NULL,

    PRIMARY KEY (id)

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='考勤规则';


CREATE TABLE attendance_punch
(
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    employee_id   BIGINT          NOT NULL,

    punch_date    DATE            NOT NULL,
    punch_time    TIME            NOT NULL,

    -- check_in / check_out
    punch_type    VARCHAR(20)     NOT NULL, #1上班 2下班

    latitude      DECIMAL(10, 7)  NULL,
    longitude     DECIMAL(10, 7)  NULL,
    location_text VARCHAR(255)    NULL,

    remark        VARCHAR(255)    NULL,

    created_by    BIGINT UNSIGNED NULL,
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_by    BIGINT UNSIGNED NULL,
    updated_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    deleted_at    DATETIME        NULL,

    PRIMARY KEY (id)

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='打卡表';


CREATE TABLE attendance_record
(
    id          BIGINT       NOT NULL AUTO_INCREMENT,

    employee_id BIGINT       NOT NULL,

    punch_date  DATE         NOT NULL,
    start_time  TIME         NULL,
    end_time    TIME         NULL,

    remark      VARCHAR(255) NULL,

    created_by  BIGINT       NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_by  BIGINT       NULL,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    deleted_at  DATETIME     NULL,

    PRIMARY KEY (id)

) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
    COMMENT ='考勤表';
