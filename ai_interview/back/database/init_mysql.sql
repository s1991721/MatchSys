-- AI Interview database/schema bootstrap for MySQL.
--
-- Before running this script, replace the password placeholder below with the
-- same value used for AI_INTERVIEW_DB_PASSWORD in the backend's local .env.
-- This script is intentionally non-destructive and can be run more than once.

CREATE DATABASE IF NOT EXISTS `ai_interview`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
