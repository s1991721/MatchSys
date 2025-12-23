CREATE TABLE attendance_policy (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  employee_id      BIGINT  NOT NULL,

  work_start_time  TIME NOT NULL,
  work_end_time    TIME NOT NULL,

  location_name    VARCHAR(100) NOT NULL,
  latitude         DECIMAL(10,7) NOT NULL,
  longitude        DECIMAL(10,7) NOT NULL,
  radius_meters    INT UNSIGNED NOT NULL DEFAULT 200,

  remark           VARCHAR(255) NULL,

  created_by       BIGINT UNSIGNED NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_by       BIGINT UNSIGNED NULL,
  updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP,
  deleted_at       DATETIME NULL,

  PRIMARY KEY (id),
  UNIQUE KEY uk_policy_employee (employee_id),

  CONSTRAINT fk_policy_employee
    FOREIGN KEY (employee_id) REFERENCES employee(id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;


CREATE TABLE attendance_punch (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

  employee_id   BIGINT  NOT NULL,

  punch_date    DATE NOT NULL,
  punch_time    TIME NOT NULL,

  -- check_in / check_out
  punch_type    VARCHAR(20) NOT NULL, #1上班 2下班

  latitude      DECIMAL(10,7) NULL,
  longitude     DECIMAL(10,7) NULL,
  location_text VARCHAR(255) NULL,

  created_by    BIGINT UNSIGNED NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  updated_by    BIGINT UNSIGNED NULL,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                           ON UPDATE CURRENT_TIMESTAMP,

  deleted_at    DATETIME NULL,

  PRIMARY KEY (id),

  KEY idx_punch_employee_date (employee_id, punch_date),
  KEY idx_punch_employee_time (employee_id, punch_time),
  KEY idx_punch_type_time (punch_type, punch_time),

  CONSTRAINT fk_punch_employee
    FOREIGN KEY (employee_id) REFERENCES employee(id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;


CREATE TABLE attendance_record (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

  employee_id  BIGINT  NOT NULL,

  punch_date   DATE NOT NULL,
  start_time   TIME  NULL,
  end_time     TIME  NULL,

  remark       VARCHAR(255) NULL,

  created_by   BIGINT UNSIGNED NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  updated_by   BIGINT UNSIGNED NULL,
  updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                          ON UPDATE CURRENT_TIMESTAMP,

  deleted_at   DATETIME NULL,

  PRIMARY KEY (id),

  KEY idx_record_employee_date (employee_id, punch_date),

  CONSTRAINT fk_record_employee
    FOREIGN KEY (employee_id) REFERENCES employee(id)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
