from pathlib import Path
import subprocess


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
