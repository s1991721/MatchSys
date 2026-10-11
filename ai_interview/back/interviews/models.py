from django.db import models

# 表结构以 database/init_mysql.sql 为准，managed=False 禁止迁移管理这些业务表。
# 关联由应用层校验；ORM 关系使用 db_constraint=False，不增加数据库外键。


class AuditModel(models.Model):
    """业务表通用审计字段；抽象模型自身不创建数据表。"""

    created_by = models.BigIntegerField(null=True)
    created_at = models.DateTimeField()
    updated_by = models.BigIntegerField(null=True)
    updated_at = models.DateTimeField()
    # NULL 表示有效记录；软删除时写入时间，查询入口统一排除已删除记录。
    deleted_at = models.DateTimeField(null=True)

    class Meta:
        abstract = True


class UserQuota(AuditModel):
    """已有企业额度记录，由其他模块初始化，本模块只读取和扣减。"""

    user_id = models.BigIntegerField(unique=True)
    remaining_count = models.PositiveBigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "user_quota"


class Interview(AuditModel):
    """面试邀请及运行快照，对应 SQL 手动维护的 interview 表。"""

    user_id = models.BigIntegerField()
    # SQL 没有请求标识唯一约束，创建接口通过企业额度行锁检查重复请求。
    request_id = models.CharField(max_length=100)
    # 只存凭证的 SHA-256 哈希，原始凭证仅在创建或轮换时返回。
    invitation_token_hash = models.CharField(max_length=64)
    position_name = models.CharField(max_length=200)
    work_description = models.TextField()
    position_requirements = models.TextField(null=True)
    # 保存创建时的岗位与评价快照，报告按 assessment_targets 中的 ID 关联评分。
    skills = models.JSONField()
    assessment_targets = models.JSONField()
    duration_minutes = models.PositiveSmallIntegerField(default=15)
    candidate_name = models.CharField(max_length=100)
    candidate_email = models.CharField(max_length=255)
    status = models.CharField(max_length=32, default="waiting")
    invite_expires_at = models.DateTimeField()
    # 保存对象存储 key；实际播放 URL 需要后续由存储服务授权生成。
    recording_storage_key = models.CharField(max_length=1000, null=True)
    video_storage_key = models.CharField(max_length=1000, null=True)

    class Meta:
        managed = False
        db_table = "interview"


class InterviewReport(models.Model):
    """成功生成的面试报告，唯一性由写入时锁定父面试保证。"""

    # ORM 关联便于一次查询取得企业归属与候选人信息，数据库字段仍为 interview_id。
    # DO_NOTHING 禁止 ORM 级联物理删除，软删除由业务接口显式处理。
    interview = models.ForeignKey(
        Interview,
        on_delete=models.DO_NOTHING,
        db_column="interview_id",
        db_constraint=False,
        related_name="reports",
    )
    report_text = models.TextField(null=True)
    assessment_scores = models.JSONField(null=True)
    # 报告列表展示生成时间；read_at 为 NULL 时计入未读报告。
    generated_at = models.DateTimeField()
    read_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True)

    class Meta:
        managed = False
        db_table = "interview_report"
