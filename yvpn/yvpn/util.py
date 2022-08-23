"""
Utility functions
"""
import locale
import subprocess
from os import path
from pathlib import Path
from typing import Tuple
from rich.progress import Progress, SpinnerColumn, TextColumn


def get_ssh_pubkey() -> Tuple[str, str]:
    """get and return the ssh pubkey text and path"""
    key_path = path.expanduser("~/.ssh/")
    key_name = "yvpn"
    pubkey_path = f"{key_path}{key_name}.pub"
    encoding = locale.getpreferredencoding()
    try:
        pubkey = Path(pubkey_path).read_text(encoding=encoding).strip()
    except FileNotFoundError:
        subprocess.run(["ssh-keygen", "-f", f"{key_path}{key_name}", "-N", ""],
                       check=True)
        pubkey = Path(pubkey_path).read_text(encoding=encoding).strip()
    return pubkey, pubkey_path


def get_datacenter_name(name: str) -> str:
    """turn a slug into a city name"""
    slug = name[-4:-1]

    slug_to_city = {
        'ams': "Amsterdam",
        'nyc': "New York City",
        'sfo': "San Francisco",
        'sgp': "Singapore",
        'lon': "London",
        'fra': "Frankfurt",
        'tor': "Toronto",
        'blr': "Bangalore"
    }
    return slug_to_city[slug]


def get_spinner():
    """return a progress spinner"""
    spinner = Progress(SpinnerColumn(),
                       TextColumn("{task.description}[progress.description]"),
                       transient=False)
    return spinner
