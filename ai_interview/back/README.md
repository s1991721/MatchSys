# AI Interview Backend

Independent Django backend for the AI Interview product.

## Local setup

```bash
cd ai_interview/back
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env, then load it into the current shell.
set -a
source .env
set +a
python manage.py migrate
python manage.py runserver 127.0.0.1:8001
```

The development server is available at `http://127.0.0.1:8001/`.

This backend uses the same MySQL server as MatchSys, while keeping its tables
in the separate `ai_interview` database/schema. Create the database and its
dedicated user before running migrations.

Initialize the local database with an administrative MySQL account. First edit
the password placeholder in `database/init_mysql.sql`, then run:

```bash
/opt/homebrew/opt/mysql-client/bin/mysql -u root -p \
  < database/init_mysql.sql
```

Set `AI_INTERVIEW_DB_PASSWORD` in `.env` to the same password, then create the
Django tables:

```bash
set -a
source .env
set +a
python manage.py migrate
```

Production environments must provide a strong `AI_INTERVIEW_SECRET_KEY`, set
`AI_INTERVIEW_DEBUG=false`, and configure `AI_INTERVIEW_ALLOWED_HOSTS`.

### mysqlclient on Apple Silicon

If `mysqlclient` cannot find Homebrew libraries in a new virtual environment,
install the client libraries and build the driver for arm64:

```bash
brew install mysql-client pkg-config zstd openssl@3
export ARCHFLAGS="-arch arm64"
export MYSQLCLIENT_CFLAGS="-I/opt/homebrew/opt/mysql-client/include/mysql"
export MYSQLCLIENT_LDFLAGS="-L/opt/homebrew/opt/mysql-client/lib -L/opt/homebrew/opt/zstd/lib -L/opt/homebrew/opt/openssl@3/lib -lmysqlclient -lz -lzstd -lssl -lcrypto -lresolv"
python -m pip install -r requirements.txt
```
