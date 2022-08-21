"""
Functions to manage wireguard
"""
import locale
from glob import glob
from pathlib import Path
import subprocess


def refresh_keys(overwrite_existing: bool = False):
    """Check if keys exist and create them, or force them to be overwritten"""

    keys_exist = Path("/etc/wireguard/private.key").is_file() and \
                 Path("/etc/wireguard/public.key").is_file()

    if not keys_exist or overwrite_existing:

        # unlock /etc/wireguard permissions
        subprocess.run(["sudo", "chmod", "-R", "777", "/etc/wireguard"],
                       check=True)

        # generate and save fresh wireguard private key
        private_key = subprocess.run(["wg", "genkey"], capture_output=True,
                                     check=True).stdout.decode()
        enc = locale.getpreferredencoding()
        with open("/etc/wireguard/private.key", "w", encoding=enc) as key_file:
            key_file.write(private_key)

        # generate and save wireguard public key
        with subprocess.Popen(["cat", "/etc/wireguard/private.key"],
                              stdout=subprocess.PIPE) as private_key:
            public_key = subprocess.check_output(["wg", "pubkey"],
                                                 stdin=private_key.stdout).decode()
        enc = locale.getpreferredencoding()
        with open("/etc/wireguard/public.key", "w", encoding=enc) as key_file:
            key_file.write(public_key)

        # lock /etc/wireguard permissions
        subprocess.run(["sudo", "chmod", "-R", "755", "/etc/wireguard"], check=True)
        subprocess.run(["sudo", "chmod", "700", "/etc/wireguard/private.key"],
                       check=True)


def get_client_private_key() -> str:
    """get the wireguard private key"""
    subprocess.run(["sudo", "chmod", "644", "/etc/wireguard/private.key"],
                   check=True)
    enc = locale.getpreferredencoding()
    with open("/etc/wireguard/private.key", encoding=enc) as file:
        private_key = file.read().strip()
    subprocess.run(["sudo", "chmod", "600", "/etc/wireguard/private.key"],
                   check=True)
    return private_key


def configure_client(endpoint_name: str,
                     server_public_key: str,
                     server_ip: str, client_ip: str) -> None:
    """create the wireguard config"""
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
    subprocess.run(["sudo", "touch", config_file], check=True)
    subprocess.run(["sudo", "chmod", "666", config_file], check=True)
    enc = locale.getpreferredencoding()
    with open(config_file, "w", encoding=enc) as file:
        file.write("\n".join(config))
    subprocess.run(["sudo", "chmod", "600", config_file], check=True)


def config_exists(name: str) -> bool:
    interfaces = [x.split("/")[-1] for x in glob("/etc/wireguard/*.conf")]
    return name + ".conf" in interfaces
