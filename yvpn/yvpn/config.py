"""
Handle setting the two global variables the app needs.
"""
import sys
from os import environ

import requests
from requests.exceptions import InvalidSchema, MissingSchema, InvalidURL, ConnectionError
from rich.console import Console


def get_user_token() -> str:
    """Try to get token from an environment variable, ask the user otherwise"""
    try:
        return environ['TOKEN_yVPN']
    except KeyError:
        token = input("Enter token: ")
        print("Set the 'TOKEN_yVPN' environment variable to skip this in the future.")
        return token


def test_server_connection(url: str):
    try:
        header = {"token": f"{TOKEN}"}
        requests.get(url=f"{url}/status", headers=header)
    except (InvalidURL, InvalidSchema, MissingSchema, ConnectionError) as e:
        print(f"There is a problem with your server url:\n{e}")
        print(f"Ensure it is set correctly to include the http/https prefix.")
        sys.exit(1)


def get_server_url():
    try:
        url = environ['URL_yVPN']
        test_server_connection(url)
        return url
    except KeyError:
        url = input("Enter server url: ")
        test_server_connection(url)
        print("Set the 'URL_yVPN' environment variable to skip this in the future.")
        return url


TOKEN = get_user_token()
SERVER_URL = get_server_url()
console = Console()
