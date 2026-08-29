# AI Interview Backend

Independent Django backend for the AI Interview product.

## Local setup

```bash
cd ai_interview/back
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The development server is available at `http://127.0.0.1:8000/` by default.

Production environments must provide a strong `DJANGO_SECRET_KEY`, set
`DJANGO_DEBUG=false`, and configure `DJANGO_ALLOWED_HOSTS`.
