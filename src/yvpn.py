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
def create(region: str = 'random'):
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


@app.command()
def connect(endpoint_name: str):
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


@app.command()
def status():
    """display connection, usage and endpoint info"""

    header = {"token": f"{TOKEN}"}
    status = requests.get(url=f"{SERVER_URL}/status",
                          headers=header).json()
    for endpoint in status:
        print(endpoint)


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

        # delete old wireguard keys and config
        subprocess.run(["sudo", "rm", "/etc/wireguard/*"])

        # generate fresh wireguard client keys
        subprocess.run(["wg", "genkey", "|", "sudo", "tee",
                        "/etc/wireguard/private.key", "|",
                        "wg", "pubkey", "|", "sudo", "tee",
                        "/etc/wireguard/public.key", "|",
                        "echo", ">", "/dev/null"])  # hack: can't seem to write directly to public.key

        # lockdown key files
        subprocess.run(["sudo", "chmod", "600", "/etc/wireguard/private.key",
                        "&&", "sudo", "chmod", "644", "/etc/wireguard/public.key"])


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
