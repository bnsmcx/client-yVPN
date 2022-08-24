"""
Functions that make requests to the yvpn server.
"""
import sys

import requests
from yvpn.config import TOKEN, SERVER_URL, console


def get_first_endpoint():
    """return the name of a user's first endpoint"""
    header = {"token": f"{TOKEN}"}
    endpoints = requests.get(url=f"{SERVER_URL}/status",
                             headers=header).json()
    return endpoints[0]["endpoint_name"]


def handle_endpoint_name_or_number(user_input: str) -> str:
    """allow a user to select an endpoint by name or number"""
    header = {"token": f"{TOKEN}"}
    endpoints: dict = requests.get(url=f"{SERVER_URL}/status",
                                   headers=header).json()

    # if it's not an appropriate number, it must be a name or user error
    if not user_input.isnumeric() or int(user_input) > len(endpoints):
        return user_input

    return endpoints[int(user_input)]["endpoint_name"]


def get_datacenter_regions() -> list:
    """return a list of available datacenters"""
    print("Getting a list of available datacenters ...")
    header = {"token": f"{TOKEN}"}
    regions = requests.get(url=f"{SERVER_URL}/datacenters",
                           headers=header).json()["available"]

    return regions


def create_token(funds: int, expiration: int, admin: bool) -> str:
    """create a new token and return it"""
    header = {"token": f"{TOKEN}"}
    request = requests.post(url=f"{SERVER_URL}/tokens",
                            json={"funds": f"{first}",
                                  "days_till_expiration": f"{expiration}",
                                  "admin": f"{admin}"},
                            headers=header)

    if request.status_code != 200:
        console.print(request.json())
        sys.exit(1)

    return request.json()["token"]


def get_all_tokens() -> list:
    """get all the tokens and their info"""
    header = {"token": f"{TOKEN}"}
    request = requests.get(url=f"{SERVER_URL}/tokens",
                           headers=header)

    if request.status_code != 200:
        console.print(request.json())
        sys.exit(1)

    token_info = request.json()
    return token_info


def delete_token(token: str):
    """delete a token"""
    header = {"token": f"{TOKEN}"}
    request = requests.delete(url=f"{SERVER_URL}/tokens",
                              params={'token_to_delete': f'{token}'},
                              headers=header)
    if request.status_code != 200:
        console.print(request.json())
        sys.exit(1)
