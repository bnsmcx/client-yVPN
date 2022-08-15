#! /usr/bin/env python3

from glob import glob
import typer
import requests
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from yvpn.util import *
from yvpn.config import SERVER_URL, TOKEN

app = typer.Typer(no_args_is_help=True,
                  add_completion=False)


@app.command()
def create(region: str = typer.Argument("random")):
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
        destroy(endpoint_name)
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
def connect(endpoint_name: str = typer.Argument(get_first_endpoint)):
    """CONNECT to your active endpoint"""
    endpoint_name = handle_endpoint_name_or_number(endpoint_name)
    disconnect()
    command = subprocess.run(["sudo", "wg-quick", "up", endpoint_name],
                             capture_output=True)

    if not command.returncode == 0:
        print(command.stderr)
    print(f"[bold green]Connected to {endpoint_name}")


@app.command()
def disconnect():
    """DISCONNECT from your endpoint"""
    endpoints = glob("/etc/wireguard/*.conf")
    for endpoint in endpoints:
        subprocess.run(["sudo", "wg-quick", "down", endpoint],
                       capture_output=True)


@app.command()
def clean():
    """DELETE and REFRESH all keys, DESTROY all endpoints"""
    disconnect()
    endpoints = glob("/etc/wireguard/*.conf")
    refresh_wireguard_keys(True)
    for endpoint in endpoints:
        destroy(endpoint.replace('.conf', "").replace("/etc/wireguard/", ""))


@app.command()
def destroy(endpoint_name: str = typer.Argument(get_first_endpoint)):
    """permanently DESTROY your endpoint"""

    disconnect()
    endpoint_name = handle_endpoint_name_or_number(endpoint_name)
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
    server_status = requests.get(url=f"{SERVER_URL}/status",
                          headers=header)

    if server_status.status_code != 200:
        print("[red bold]There was a problem:", server_status.json())
        exit(1)

    active_connection = subprocess.run(["sudo", "wg", "show"],
                                       capture_output=True)

    connection_info = Panel.fit("[bold]Not connected.")
    if active_endpoint := active_connection.stdout:
        active_endpoint = active_endpoint.decode().split()[1]
        connection_info = Panel.fit(f"[bold cyan]Connected to: {active_endpoint}",)

    endpoint_table = Table()

    endpoint_table.add_column("Number", justify="center")
    endpoint_table.add_column("Name", justify="center")
    endpoint_table.add_column("Location", justify="center")
    endpoint_table.add_column("Created", justify="center")

    for index, endpoint in enumerate(server_status.json()):
        name = endpoint["endpoint_name"]
        location = get_datacenter_name(name)
        endpoint_style = "bold"
        if active_endpoint == name:
            endpoint_style = "bold green"
        endpoint_table.add_row(str(index), name, location, "TODO",
                      style=endpoint_style)

    billing_table = Table()

    billing_table.add_column("Token", justify='center')
    billing_table.add_column("Expiration", justify='center')
    billing_table.add_column("Balance", justify='center')
    billing_table.add_row("TODO", "TODO", "TODO")

    console = Console()
    console.print(connection_info, justify="center")
    console.print(endpoint_table, justify="center")
    console.print(billing_table, justify="center")


def main():
    app()


if __name__ == "__main__":
    main()
