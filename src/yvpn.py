#! /usr/bin/env python3

from os import environ, path
import socket
import subprocess
from glob import glob
import time
from pathlib import Path
from typing import Tuple

import requests

import typer
import paramiko
from rich import print
from rich.panel import Panel
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(no_args_is_help=True,
                  add_completion=False)
SERVER_URL = "http://127.0.0.1:8000"


def get_user_token() -> str:
    try:
        return environ['TOKEN_yVPN']
    except KeyError:
        token = typer.prompt("Enter token")
        print("Set the 'TOKEN_yVPN' environment variable to skip this in the future.")
        return token


def get_ssh_pubkey() -> Tuple[str, str]:
    key_path = path.expanduser("~/.ssh/")
    key_name = "yvpn"
    pubkey_path = f"{key_path}{key_name}.pub"
    try:
        pubkey = Path(pubkey_path).read_text().strip()
    except FileNotFoundError:
        subprocess.run(["ssh-keygen", "-f", f"{key_path}{key_name}", "-N", ""])
        pubkey = Path(pubkey_path).read_text().strip()
    return pubkey, pubkey_path


@app.command()
def create(region: str = typer.Argument("random")):
    """CREATE a new VPN endpoint"""

    refresh_wireguard_keys()
    ssh_pubkey, ssh_pubkey_path = get_ssh_pubkey()

    with get_spinner() as spinner:
        spinner.add_task("Creating the endpoint, this could take a minute.")
        header = {"token": f"{TOKEN}"}
        response = requests.post(url=f"{SERVER_URL}/create",
                                 json={'region': f'{region}',
                                       'ssh_pub_key': f'{ssh_pubkey}'},
                                 headers=header)

    if response.status_code != 200:
        print(f"There was a problem:\n {response.json()}")
        exit(1)

    endpoint_ip = response.json()["server_ip"]
    endpoint_name = response.json()["endpoint_name"]
    client_ip = "10.0.0.2"  # TODO: let the user set this
    server_public_key = server_key_exchange(ssh_pubkey_path,
                                            endpoint_ip, client_ip)

    if not server_public_key:
        print("Key exchange failed.")
        destroy(endpoint_name)
        exit(1)

    configure_wireguard_client(endpoint_name,
                               server_public_key,
                               endpoint_ip,
                               client_ip)

    print("New endpoint successfully created and configured.")


@app.command()
def datacenters():
    """GET a list of available datacenters for endpoint creation"""
    print(get_datacenter_regions())


def get_first_endpoint():
    header = {"token": f"{TOKEN}"}
    endpoints = requests.get(url=f"{SERVER_URL}/status",
                                 headers=header).json()
    return endpoints[0]["endpoint_name"]


@app.command()
def connect(endpoint_name: str = typer.Argument(get_first_endpoint)):
    """CONNECT to your active endpoint"""
    disconnect()
    subprocess.run(["sudo", "wg-quick", "up", endpoint_name])


@app.command()
def disconnect():
    """DISCONNECT from your endpoint"""
    endpoints = glob("/etc/wireguard/*.conf")
    for endpoint in endpoints:
        subprocess.run(["sudo", "wg-quick", "down", endpoint],
                       capture_output=True)


@app.command()
def clean():
    """DELETE and REFRESH all keys, DESTROY all endpoints"""
    disconnect()
    endpoints = glob("/etc/wireguard/*.conf")
    for endpoint in endpoints:
        destroy(endpoint.replace('.conf', "").replace("/etc/wireguard/", ""))

    refresh_wireguard_keys(True)


@app.command()
def destroy(endpoint_name: str):
    """permanently DESTROY your endpoint"""

    # disconnect first
    disconnect()

    header = {"token": f"{TOKEN}"}
    status = requests.delete(url=f"{SERVER_URL}/endpoint",
                             headers=header,
                             params={'endpoint_name': f'{endpoint_name}'})

    if status.status_code == 200:
        sp = subprocess.run(["sudo", "rm", f"/etc/wireguard/{endpoint_name}.conf"],
                       capture_output=True)
        if sp.returncode == 0:
            print(f"{endpoint_name} successfully deleted.")
        else:
            print(f"{endpoint_name} deleted but couldn't delete the wireguard config.")
    else:
        print(f"Problem deleting {endpoint_name}:\n {status.json()}")


def get_datacenter_name(name: str) -> str:
    slug = name[-4:-1]

    match slug:
        case 'ams':
            return "Amsterdam"
        case 'nyc':
            return "New York City"
        case 'sfo':
            return "San Francisco"
        case 'sgp':
            return "Singapore"
        case 'lon':
            return "London"
        case 'fra':
            return "Frankfurt"
        case 'tor':
            return "Toronto"
        case 'blr':
            return "Bangalore"


@app.command()
def status():
    """display connection, usage and endpoint info"""

    header = {"token": f"{TOKEN}"}
    server_status = requests.get(url=f"{SERVER_URL}/status",
                          headers=header).json()
    active_connection = subprocess.run(["sudo", "wg", "show"],
                                       capture_output=True)

    connection_info = Panel.fit("[bold]Not connected.")
    if active_endpoint := active_connection.stdout:
        active_endpoint = active_endpoint.decode().split()[1]
        connection_info = Panel.fit(f"[bold cyan]Connected to: {active_endpoint}",)

    endpoint_table = Table()

    endpoint_table.add_column("Number", justify="center")
    endpoint_table.add_column("Name", justify="center")
    endpoint_table.add_column("Location", justify="center")
    endpoint_table.add_column("Created", justify="center")

    for index, endpoint in enumerate(server_status):
        name = endpoint["endpoint_name"]
        location = get_datacenter_name(name)
        endpoint_style = "bold"
        if active_endpoint == name:
            endpoint_style = "bold green"
        endpoint_table.add_row(str(index), name, location, "TODO",
                      style=endpoint_style)

    billing_table = Table()

    billing_table.add_column("Token", justify='center')
    billing_table.add_column("Expiration", justify='center')
    billing_table.add_column("Balance", justify='center')
    billing_table.add_row("TODO", "TODO", "TODO")

    console = Console()
    console.print(connection_info, justify="center")
    console.print(endpoint_table, justify="center")
    console.print(billing_table, justify="center")


def endpoint_server_up(server_ip: str) -> bool:
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        connection.connect((server_ip, 22))
        connection.shutdown(2)
        return True
    except Exception:
        return False


def get_spinner():
    spinner = Progress(SpinnerColumn(),
                       TextColumn("{task.description}[progress.description]"),
                       transient=False)
    return spinner


def server_key_exchange(ssh_pubkey_path: str, server_ip: str, client_ip: str) -> str:
    # create ssh client and connect
    with get_spinner() as spinner:
        spinner.add_task("Waiting for server to come up...")
        while not endpoint_server_up(server_ip):
            time.sleep(1)

    ssh_key = ssh_pubkey_path.replace(".pub", "")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        with get_spinner() as spinner:
            spinner.add_task("Performing key exchange with new VPN endpoint ...")
            ssh.connect(server_ip, username="root",
                        key_filename=ssh_key,
                        look_for_keys=False,
                        banner_timeout=60,
                        timeout=60,
                        auth_timeout=60)

        # activate client on server
        client_public_key = Path("/etc/wireguard/public.key").read_text().strip()
        command = f"wg set wg0 peer {client_public_key} allowed-ips {client_ip}"
        ssh.exec_command(command)

        # get and return server public key
        (stdin, stdout, stderr) = ssh.exec_command("cat /etc/wireguard/public.key")
        server_public_key = stdout.read().decode().strip()

        return server_public_key

    except Exception as e:
        print(e)


def refresh_wireguard_keys(overwrite_existing: bool = False):

    keys_exist = Path("/etc/wireguard/private.key").is_file() and \
                 Path("/etc/wireguard/public.key").is_file()

    if not keys_exist or overwrite_existing:

        # unlock /etc/wireguard permissions
        subprocess.run(["sudo", "chmod", "-R", "777", "/etc/wireguard"])

        # generate and save fresh wireguard private key
        private_key = subprocess.run(["wg", "genkey"], capture_output=True)\
            .stdout.decode()
        with open("/etc/wireguard/private.key", "w") as key_file:
            key_file.write(private_key)

        # generate and save wireguard public key
        private_key = subprocess.Popen(["cat", "/etc/wireguard/private.key"],
                                       stdout=subprocess.PIPE)
        public_key = subprocess.check_output(["wg", "pubkey"],
                                             stdin=private_key.stdout).decode()
        with open("/etc/wireguard/public.key", "w") as key_file:
            key_file.write(public_key)

        # lock /etc/wireguard permissions
        subprocess.run(["sudo", "chmod", "-R", "755", "/etc/wireguard"])
        subprocess.run(["sudo", "chmod", "700", "/etc/wireguard/private.key"])


def get_client_private_key() -> str:
    subprocess.run(["sudo", "chmod", "644", "/etc/wireguard/private.key"])
    with open("/etc/wireguard/private.key") as f:
        private_key = f.read().strip()
    subprocess.run(["sudo", "chmod", "600", "/etc/wireguard/private.key"])
    return private_key


def configure_wireguard_client(endpoint_name: str,
                               server_public_key: str,
                               server_ip: str, client_ip: str) -> None:
    print("Setting up local configuration ...")

    config = ("[Interface]",
              f"PrivateKey = {get_client_private_key()}",
              f"Address = {client_ip}/24",
              "\n",
              "[Peer]",
              f"PublicKey = {server_public_key}",
              f"Endpoint = {server_ip}:51820",
              "AllowedIPs = 0.0.0.0/0",
              "\n"
              )

    config_file = f"/etc/wireguard/{endpoint_name}.conf"
    subprocess.run(["sudo", "touch", config_file])
    subprocess.run(["sudo", "chmod", "666", config_file])
    with open(config_file, "w") as f:
        f.write("\n".join(config))
    subprocess.run(["sudo", "chmod", "600", config_file])


def get_datacenter_regions() -> list:
    print("Getting a list of available datacenters ...")
    header = {"token": f"{TOKEN}"}
    regions = requests.get(url=f"{SERVER_URL}/datacenters",
                           headers=header).json()["available"]

    return regions


if __name__ == "__main__":
    TOKEN = get_user_token()
    app()
