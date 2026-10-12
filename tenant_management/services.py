"""Platform operations use dedicated connections, never change business routing."""
import copy
import json
import re
from contextlib import contextmanager

from django.db import connections
from django.db.backends.mysql.base import DatabaseWrapper

PREFIX = 'matchsys_'
LEGACY_PREFIX = 'matchsys_tenant_'
MARKER = 'tenant_profile'


def normalize_domain(value):
    try:
        domain = value.strip().lower().encode('idna').decode('ascii')
    except UnicodeError:
        raise ValueError('请输入有效的邮箱域名')
    if len(domain) > 253 or '.' not in domain or any(
        not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
        for label in domain.split('.')
    ):
        raise ValueError('请输入有效的邮箱域名，例如 company.com')
    return domain


def schema_name(domain):
    domain = normalize_domain(domain)
    if not domain.endswith('.com') or domain.count('.') != 1:
        raise ValueError('邮箱域名必须为 XXXX.com')
    suffix = domain[:-4]
    name = PREFIX + suffix
    if len(name) > 64:
        raise ValueError('邮箱域名过长，生成的 Schema 名称不能超过 64 个字符')
    return name


def quote(value):
    return '`' + value.replace('`', '``') + '`'


@contextmanager
def database(name=None):
    config = copy.deepcopy(connections['default'].settings_dict)
    if name is not None:
        config['NAME'] = name
    db = DatabaseWrapper(config, alias='platform_operation')
    try:
        yield db
    finally:
        db.close()


def list_tenants():
    result = []
    with database() as db, db.cursor() as cursor:
        cursor.execute('SHOW DATABASES')
        names = [row[0] for row in cursor.fetchall()]
        for name in names:
            if not name.startswith(PREFIX):
                continue
            cursor.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s', [name, MARKER])
            if not cursor.fetchone():
                continue
            cursor.execute(f'SELECT company_name, email_domain FROM {quote(name)}.{quote(MARKER)} WHERE id=1')
            row = cursor.fetchone()
            if row:
                result.append({'company_name': row[0], 'email_domain': row[1], 'managed': True})
        # Existing installation remains visible without changing its data.
        cursor.execute("SELECT settings FROM sys_settings WHERE name='company-info' AND deleted_at IS NULL LIMIT 1")
        row = cursor.fetchone()
        if row:
            info = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            email = str(info.get('mail') or '')
            result.insert(0, {'company_name': info.get('company_name') or '现有公司',
                             'email_domain': email.rsplit('@', 1)[1] if '@' in email else '未配置',
                             'managed': False})
        elif source_name := connections['default'].settings_dict['NAME']:
            result.insert(0, {'company_name': source_name, 'email_domain': '未配置', 'managed': False})
    return result


def validate_password(password):
    if not password or len(password) > 255:
        raise ValueError('管理员密码不能为空，且不能超过 255 个字符')


def create_tenant(company_name, domain, password):
    company_name = company_name.strip()
    if not company_name or len(company_name) > 100:
        raise ValueError('公司名不能为空，且不能超过 100 个字符')
    domain = normalize_domain(domain)
    name = schema_name(domain)
    validate_password(password)
    if len('admin@' + domain) > 100:
        raise ValueError('管理员邮箱超过现有账号字段长度限制')
    if any(item['email_domain'].lower() == domain for item in list_tenants()):
        raise ValueError('该邮箱域名已经属于一个租户')
    source = connections['default'].settings_dict['NAME']
    with database() as db, db.cursor() as cursor:
        # No IF NOT EXISTS: a concurrent create must fail rather than overwrite.
        cursor.execute(f'CREATE DATABASE {quote(name)} CHARACTER SET utf8mb4')
    try:
        with database(name) as db, db.cursor() as cursor:
            cursor.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE=%s', [source, 'BASE TABLE'])
            tables = [row[0] for row in cursor.fetchall() if row[0] != MARKER]
            cursor.execute('SET FOREIGN_KEY_CHECKS=0')
            for table in tables:
                cursor.execute(f'SHOW CREATE TABLE {quote(source)}.{quote(table)}')
                ddl = cursor.fetchone()[1].replace(f'{quote(source)}.', f'{quote(name)}.')
                ddl = re.sub(r' AUTO_INCREMENT=\d+', '', ddl)
                cursor.execute(ddl)
            cursor.execute('SET FOREIGN_KEY_CHECKS=1')
            # Only reusable navigation is copied; no customer business data.
            cursor.execute(f'INSERT INTO sys_menu SELECT * FROM {quote(source)}.sys_menu WHERE deleted_at IS NULL')
            cursor.execute("INSERT INTO sys_role (id, role_name, description, menu_list, created_at, updated_at) VALUES (999, '管理员', '公司管理员', '*', NOW(), NOW())")
            cursor.execute("INSERT INTO employee (id, name, email, department_name, position_name, status, created_by, updated_by, created_at, updated_at) VALUES (1, '公司管理员', %s, '系统管理', '管理员', 1, 1, 1, NOW(), NOW())", ['admin@' + domain])
            # MatchSys currently compares company passwords directly.
            cursor.execute("INSERT INTO user_login (employee_id, employee_name, user_name, password, role_id, menu_list, created_at, updated_at) VALUES (1, '公司管理员', %s, %s, 999, '[\"*\"]', NOW(), NOW())", ['admin@' + domain, password])
            cursor.execute("INSERT INTO sys_settings (name, settings, created_at, updated_at) VALUES ('company-info', %s, NOW(), NOW())", [json.dumps({'company_name': company_name, 'mail': 'admin@' + domain})])
            cursor.execute(f'CREATE TABLE {quote(MARKER)} (id INT PRIMARY KEY, company_name VARCHAR(100) NOT NULL, email_domain VARCHAR(253) NOT NULL, admin_employee_id BIGINT NOT NULL)')
            cursor.execute(f'INSERT INTO {quote(MARKER)} VALUES (1, %s, %s, 1)', [company_name, domain])
    except Exception:
        # Only the new schema created by this invocation is rolled back.
        with database() as db, db.cursor() as cursor:
            cursor.execute(f'DROP DATABASE {quote(name)}')
        raise


def managed_schema(domain):
    domain = normalize_domain(domain)
    name = schema_name(domain)
    # Existing tenants remain manageable under the previous naming convention.
    legacy_name = LEGACY_PREFIX + domain.replace('-', '_h').replace('.', '_d')
    with database() as db, db.cursor() as cursor:
        cursor.execute('SHOW DATABASES')
        names = {row[0] for row in cursor.fetchall()}
    if name not in names and legacy_name in names:
        name = legacy_name
    if name == connections['default'].settings_dict['NAME']:
        raise ValueError('不能从租户管理页面操作当前业务数据库')
    with database(name) as db, db.cursor() as cursor:
        cursor.execute(f'SELECT email_domain FROM {quote(MARKER)} WHERE id=1')
        row = cursor.fetchone()
        if not row or row[0] != domain:
            raise ValueError('租户信息不匹配')
    return name


def update_password(domain, password):
    validate_password(password)
    name = managed_schema(domain)
    with database(name) as db, db.cursor() as cursor:
        cursor.execute(f'SELECT employee_id FROM user_login WHERE employee_id=(SELECT admin_employee_id FROM {quote(MARKER)} WHERE id=1) AND deleted_at IS NULL')
        if not cursor.fetchone():
            raise ValueError('未找到租户管理员')
        cursor.execute(f'UPDATE user_login SET password=%s, password_expires_at=NULL, updated_at=NOW() WHERE employee_id=(SELECT admin_employee_id FROM {quote(MARKER)} WHERE id=1) AND deleted_at IS NULL', [password])


def delete_tenant(domain):
    name = managed_schema(domain)
    with database() as db, db.cursor() as cursor:
        cursor.execute(f'DROP DATABASE {quote(name)}')
