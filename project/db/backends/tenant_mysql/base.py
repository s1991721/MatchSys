from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper
from django.db.utils import DatabaseError

from project.tenancy import current_schema


class DatabaseWrapper(MySQLDatabaseWrapper):
    """Select tenant at connection creation; covers ORM, SQL, and transactions."""
    _connected_schema = None

    def get_connection_params(self):
        if current_schema() == '!':
            raise DatabaseError('A tenant domain is required for business database access')
        params = super().get_connection_params()
        schema = current_schema() or self.settings_dict['NAME']
        params['database'] = schema
        self._connected_schema = schema
        return params

    def ensure_connection(self):
        if current_schema() == '!':
            raise DatabaseError('A tenant domain is required for business database access')
        schema = current_schema() or self.settings_dict['NAME']
        if self.connection is not None and self._connected_schema != schema:
            if self.in_atomic_block:
                raise DatabaseError('Cannot change tenant inside a transaction')
            self.close()
        super().ensure_connection()
