from django.contrib.auth.hashers import check_password
from django.utils.crypto import constant_time_compare


# Fixed platform credentials; independent of company users and databases.
# Initial password: MatchSys@2026. Change the hash here before deployment.
ADMIN_USERNAME = "platform_admin"
ADMIN_PASSWORD_HASH = "pbkdf2_sha256$870000$e1P4pcu3MNpQrQh2Ujyafx$HkPXJ50cn8iGYCAmLAN9K6IRhiJyghfC0jpXC1e7Crk="


def authenticate(username, password):
    password_matches = check_password(password, ADMIN_PASSWORD_HASH)
    return constant_time_compare(username, ADMIN_USERNAME) and password_matches
