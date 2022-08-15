import subprocess
from os import path
from pathlib import Path
from typing import Tuple
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


def get_spinner():
    spinner = Progress(SpinnerColumn(),
                       TextColumn("{task.description}[progress.description]"),
                       transient=False)
    return spinner
