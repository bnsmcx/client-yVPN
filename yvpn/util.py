import subprocess
from os import path
import socket
import time
from pathlib import Path
from typing import Tuple
import paramiko
from rich.progress import Progress, SpinnerColumn, TextColumn


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
        private_key = subprocess.run(["wg", "genkey"], capture_output=True) \
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


