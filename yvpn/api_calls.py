import requests
from yvpn.config import TOKEN, SERVER_URL


def get_first_endpoint():
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
    print("Getting a list of available datacenters ...")
    header = {"token": f"{TOKEN}"}
    regions = requests.get(url=f"{SERVER_URL}/datacenters",
                           headers=header).json()["available"]

    return regions
