import os
import time
from pathlib import Path

import requests

import typer
import paramiko

app = typer.Typer()
SERVER_URL = "http://127.0.0.1:8000"


def get_ssh_pubkey(ssh_pub_key_path: str) -> str:
    return Path(ssh_pub_key_path).read_text().strip()


@app.command()
def create(token: str, ssh_pub_key_path: str, region: str = 'random'):
    """CREATE a new VPN endpoint"""

    print("Asking the server to create the endpoint, this could take a minute.")
    header = {"token": f"{token}"}
    response = requests.post(url=f"{SERVER_URL}/create",
                              json={'region': f'{region}',
                                    'ssh_pub_key': f'{get_ssh_pubkey(ssh_pub_key_path)}'},
                              headers=header)

    if response.status_code != 200:
        print(f"There was a problem:\n {response.json()}")
        exit(1)

    server_ip = response.json()["server_ip"]
    client_ip = "10.0.0.2"  # TODO: let the user set this
    refresh_client_keys()
    server_public_key = server_key_exchange(ssh_pub_key_path, server_ip, client_ip)

    if server_public_key is None:
        print("Key exchange failed.")
        exit(1)

    configure_wireguard_client(server_public_key, server_ip, client_ip)

    print("New endpoint successfully created and configured.")


@app.command()
def connect():
    """CONNECT to your active endpoint"""
    os.system("sudo wg-quick up wg0")


@app.command()
def disconnect():
    """DISCONNECT from your endpoint"""
    os.system("sudo wg-quick down wg0")


@app.command()
def destroy(token: str, endpoint_name: str):
    """permanently DESTROY your endpoint"""

    header = {"token": f"{token}"}
    status = requests.delete(url=f"{SERVER_URL}/endpoint",
                             headers=header,
                             params={'endpoint_name': f'{endpoint_name}'})

    if status.status_code == 200:
        print(f"{endpoint_name} successfully deleted.")
    else:
        print(f"Problem deleting {endpoint_name}:\n {status.json()}")


@app.command()
def status(token: str):
    """display connection, usage and endpoint info"""

    header = {"token": f"{token}"}
    status = requests.get(url=f"{SERVER_URL}/status",
                          headers=header).json()
    print(status)


def server_key_exchange(ssh_pubkey_path: str, server_ip: str, client_ip: str) -> str:
    # create ssh client and connect
    print("VPN endpoint created, performing key exchange (up to a minute)...")
    ssh_key = ssh_pubkey_path.replace(".pub", "")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(server_ip, username="root",
                    key_filename=ssh_key,
                    look_for_keys=False,
                    banner_timeout=60)

        # activate client on server
        print("Performing key exchange with new VPN endpoint ...")
        client_public_key = Path("/etc/wireguard/public.key").read_text().strip()
        command = f"wg set wg0 peer {client_public_key} allowed-ips {client_ip}"
        ssh.exec_command(command)

        # get and return server public key
        (stdin, stdout, stderr) = ssh.exec_command("cat /etc/wireguard/public.key")
        server_public_key = stdout.read().decode().strip()

        print("Key exchange complete ...")
        return server_public_key

    except Exception as e:
        print(e)


def refresh_client_keys():
    # delete old wireguard keys and config
    os.system("sudo rm /etc/wireguard/*")

    # generate fresh wireguard client keys
    os.system("wg genkey | " + \
              "sudo tee /etc/wireguard/private.key | " + \
              "wg pubkey | sudo tee /etc/wireguard/public.key | " + \
              "echo > /dev/null")  # hack: can't seem to write directly to public.key

    # lockdown key files
    os.system("sudo chmod 600 /etc/wireguard/private.key && " + \
              "sudo chmod 644 /etc/wireguard/public.key")


def get_client_private_key() -> str:
    os.system("sudo chmod 644 /etc/wireguard/private.key")
    with open("/etc/wireguard/private.key") as f:
        private_key = f.read().strip()
    os.system("sudo chmod 600 /etc/wireguard/private.key")
    return private_key


def configure_wireguard_client(server_public_key: str,
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

    config_file = "/etc/wireguard/wg0.conf"
    os.system(f"sudo touch {config_file}")
    os.system(f"sudo chmod 666 {config_file}")
    with open(config_file, "w") as f:
        f.write("\n".join(config))
    os.system(f"sudo chmod 600 {config_file}")


def get_datacenter_regions(token: str) -> list:
    print("Getting a list of available datacenters ...")
    header = {"token": f"{token}"}
    regions = requests.get(url=f"{SERVER_URL}/datacenters",
                               headers=header).json()["available"]

    return regions


def spinning_cursor():
    while True:
        for cursor in '|/-\\':
            yield cursor


if __name__ == "__main__":
    app()
