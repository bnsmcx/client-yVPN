"""
Functions to handle communication with an endpoint.
"""
import locale
from pathlib import Path
import socket
import time
import paramiko
from yvpn.util import get_spinner


def key_exchange(ssh_pubkey_path: str, server_ip: str, client_ip: str) -> str:
    """exchange wireguard keys via ssh"""

    with get_spinner() as spinner:
        spinner.add_task("Waiting for server to come up...")
        while not endpoint_server_up(server_ip):
            time.sleep(1)

    ssh_key = ssh_pubkey_path.replace(".pub", "")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    with get_spinner() as spinner:
        spinner.add_task("Performing key exchange with new VPN endpoint ...")
        ssh.connect(server_ip, username="root",
                    key_filename=ssh_key,
                    look_for_keys=False,
                    banner_timeout=60,
                    timeout=60,
                    auth_timeout=60)

    # activate client on server
    encoding = locale.getpreferredencoding()
    client_public_key = Path("/etc/wireguard/public.key")\
        .read_text(encoding=encoding).strip()
    command = f"wg set wg0 peer {client_public_key} allowed-ips {client_ip}"
    ssh.exec_command(command)

    # get and return server public key
    _, stdout, _ = ssh.exec_command("cat /etc/wireguard/public.key")
    server_public_key = stdout.read().decode().strip()

    return server_public_key


def endpoint_server_up(server_ip: str) -> bool:
    """Check and see if an ssh server is up"""
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        connection.connect((server_ip, 22))
        connection.shutdown(2)
        return True
    except ConnectionRefusedError:
        return False
