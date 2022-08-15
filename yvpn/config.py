"""
Handle setting the two global variables the app needs.
"""

from os import environ


def get_user_token() -> str:
    """Try to get token from an environment variable, ask the user otherwise"""
    try:
        return environ['TOKEN_yVPN']
    except KeyError:
        token = input("Enter token")
        print("Set the 'TOKEN_yVPN' environment variable to skip this in the future.")
        return token


SERVER_URL = "http://127.0.0.1:8000"
TOKEN = get_user_token()
