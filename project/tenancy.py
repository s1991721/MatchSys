"""Request/task-local tenant identity used by every default database operation."""
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from functools import wraps

from django.db import connections

_domain = ContextVar('matchsys_tenant_domain', default=None)
_schema = ContextVar('matchsys_tenant_schema', default=None)
COOKIE = 'matchsys_tenant'
SALT = 'matchsys.tenant'
TASK_SALT = 'matchsys.tenant.task'
TASK_PATHS = {'/api/time-to-save', '/api/time-to-save-day', '/api/time-to-clean',
              '/api/time-to-backup', '/api/time-to-hello', '/api/time-to-sync-my-mails'}


def current_domain():
    return _domain.get()


def current_schema():
    return _schema.get()


@contextmanager
def tenant_context(domain, schema=None):
    from tenant_management.services import schema_name
    domain_token = _domain.set(domain)
    schema_token = _schema.set(schema or (schema_name(domain) if domain else None))
    try:
        yield
    finally:
        _schema.reset(schema_token)
        _domain.reset(domain_token)


def tenant_cache_key(key):
    return f'{current_domain() or "legacy"}:{key}'


def tenant_target(function):
    """Capture identity when creating a thread, not when the thread starts."""
    context = copy_context()
    @wraps(function)
    def run(*args, **kwargs):
        try:
            return context.run(function, *args, **kwargs)
        finally:
            connections.close_all()
    return run
