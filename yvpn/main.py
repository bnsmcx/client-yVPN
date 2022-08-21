#! /usr/bin/env python3

"""
Homebase for the typer CLI app.  This file contains only functions that
represent commands available to the user.
"""

import subprocess
import sys
from glob import glob
import requests
import typer
from rich.table import Table

from yvpn import util
from yvpn import api_calls
from yvpn import wireguard
from yvpn import endpoint
from yvpn.config import SERVER_URL, TOKEN, console

app = typer.Typer(no_args_is_help=True,
                  add_completion=False)


@app.command()
def create(region: str = typer.Argument("random")):
    """CREATE a new VPN endpoint"""

    wireguard.refresh_keys()
    ssh_pubkey, ssh_pubkey_path = util.get_ssh_pubkey()

    with util.get_spinner() as spinner:
        spinner.add_task("Creating the endpoint, this could take a minute.")
        header = {"token": f"{TOKEN}"}
        response = requests.post(url=f"{SERVER_URL}/create",
                                 json={'region': f'{region}',
                                       'ssh_pub_key': f'{ssh_pubkey}'},
                                 headers=header)

    if response.status_code != 200:
        console.print(f"There was a problem:\n {response.json()}")
        sys.exit(1)

    endpoint_ip = response.json()["server_ip"]
    endpoint_name = response.json()["endpoint_name"]
    client_ip = "10.0.0.2"
    server_public_key = endpoint.key_exchange(ssh_pubkey_path,
                                              endpoint_ip, client_ip)

    if not server_public_key:
        console.print("Key exchange failed.")
        destroy(endpoint_name)
        sys.exit(1)

    wireguard.configure_client(endpoint_name,
                               server_public_key,
                               endpoint_ip,
                               client_ip)

    console.print("New endpoint successfully created and configured.")


@app.command()
def datacenters():
    """GET a list of available datacenters for endpoint creation"""
    console.print(api_calls.get_datacenter_regions())


@app.command()
def connect(endpoint_name: str = typer.Argument(api_calls.get_first_endpoint)):
    """CONNECT to your active endpoint"""
    endpoint_name = api_calls.handle_endpoint_name_or_number(endpoint_name)
    disconnect()
    command = subprocess.run(["sudo", "wg-quick", "up", endpoint_name],
                             check=True,
                             capture_output=True)

    if not command.returncode == 0:
        console.print(command.stderr)
    console.print(f"[bold green]Connected to {endpoint_name}")


@app.command()
def disconnect():
    """DISCONNECT from your endpoint"""
    interfaces = glob("/etc/wireguard/*.conf")
    for interface in interfaces:
        try:
            subprocess.run(["sudo", "wg-quick", "down", interface],
                           check=True,
                           capture_output=True)
        except subprocess.CalledProcessError:
            # ignore error when trying to bring down an inactive interface
            continue


@app.command()
def clean():
    """DELETE and REFRESH all keys, DESTROY all endpoints"""
    disconnect()
    interfaces = glob("/etc/wireguard/*.conf")
    wireguard.refresh_keys(True)
    for interface in interfaces:
        destroy(interface.replace('.conf', "").replace("/etc/wireguard/", ""))


@app.command()
def destroy(endpoint_name: str = typer.Argument(api_calls.get_first_endpoint)):
    """permanently DESTROY your endpoint"""

    disconnect()
    endpoint_name = api_calls.handle_endpoint_name_or_number(endpoint_name)
    header = {"token": f"{TOKEN}"}
    deletion_request = requests.delete(url=f"{SERVER_URL}/endpoint",
                                       headers=header,
                                       params={'endpoint_name': f'{endpoint_name}'})

    if deletion_request.status_code == 200:
        try:
            subprocess.run(
                ["sudo", "rm", f"/etc/wireguard/{endpoint_name}.conf"],
                check=True,
                capture_output=True)
            console.print(f"{endpoint_name} successfully deleted.")
        except subprocess.CalledProcessError:
            console.print(f"{endpoint_name} deleted but couldn't delete the wireguard config.")
            console.print("This is probably because it does not exist.")
    else:
        console.print(f"Problem deleting {endpoint_name}:\n {deletion_request.json()}")


@app.command()
def status():
    """display connection, usage and endpoint info"""

    active_connection = subprocess.run(["sudo", "wg", "show"],
                                       capture_output=True,
                                       check=True)

    connection_info = "[bold]Not connected."
    token_info = "[bold]Token will be depleted on TODO at current usage."

    if active_endpoint := active_connection.stdout:
        active_endpoint = active_endpoint.decode().split()[1]
        connection_info = f"[bold green]Connected to: {active_endpoint}"

    endpoint_table = Table(caption=token_info, expand=True)

    endpoint_table.add_column("Number", justify="center")
    endpoint_table.add_column("Name", justify="center")
    endpoint_table.add_column("Location", justify="center")
    endpoint_table.add_column("Created", justify="center")

    header = {"token": f"{TOKEN}"}
    server_status = requests.get(url=f"{SERVER_URL}/status",
                                 headers=header)

    if server_status.status_code != 200:
        console.print("[red bold]There was a problem:")
        console.print_json(server_status.json())
        sys.exit(1)

    for index, endpoint_server in enumerate(server_status.json()):
        name = endpoint_server["endpoint_name"]
        if not wireguard.config_exists(name):
            match endpoint.prompt_to_fix(name):
                case "delete":
                    destroy(name)
                    sys.exit(1)
                case "repair":
                    print("TODO: Not implemented, you can only 'delete' broken endpoints")
        location = util.get_datacenter_name(name)
        endpoint_style = "bold"
        if active_endpoint == name:
            endpoint_style = "bold green"
        endpoint_table.add_row(str(index), name, location, "TODO",
                               style=endpoint_style)

    console.print()
    console.rule(connection_info)
    console.print(endpoint_table, justify="center")
    console.print()


def main():
    """The entry point into the app."""
    app()


if __name__ == "__main__":
    main()
