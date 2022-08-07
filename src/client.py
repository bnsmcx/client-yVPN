#!/usr/bin/env python
import os
from pathlib import Path

import requests

import typer
import paramiko
from getpass import getpass

app = typer.Typer()
SERVER_URL = "http://127.0.0.1:8000"


@app.command()
def create(token: str):
    """CREATE a new VPN endpoint"""
    
    header = {"token": f"{token}"}
    server_ip = requests.get(url=f"{SERVER_URL}/status",
                               headers=header).json()
    
    client_ip = "10.0.0.2"  # TODO: let the user set this

    refresh_client_keys()
    server_public_key = server_key_exchange(server_ip, client_ip)
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
                               endpoint_name=endpoint_name)

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


def server_key_exchange(server_ip: str, client_ip: str) -> str:
    # create ssh client and connect
    print("VPN endpoint server created, waiting for it to fully boot ...")
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    passphrase = getpass(prompt="id_rsa passphrase: ")

    while True:
        try:
            ssh.connect(server_ip, username="root", passphrase=passphrase)

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

        except:
            continue


def refresh_client_keys():
    # delete old wireguard keys and config
    os.system("sudo rm /etc/wireguard/*")

    # generate fresh client keys
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
    regions_raw = requests.get(url=f"{SERVER_URL}/datacenters",
                               headers=header).json()["available"]

    return regions


def spinning_cursor():
    while True:
        for cursor in '|/-\\':
            yield cursor


if __name__ == "__main__":
    app()
