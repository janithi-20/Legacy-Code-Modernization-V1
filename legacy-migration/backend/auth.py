import hmac
import os


def configured_credentials():
    return (
        os.getenv("DASHBOARD_USERNAME", "admin"),
        os.getenv("DASHBOARD_PASSWORD", "migration"),
    )


def credentials_match(username, password):
    expected_username, expected_password = configured_credentials()
    return hmac.compare_digest(username, expected_username) and hmac.compare_digest(
        password, expected_password
    )
