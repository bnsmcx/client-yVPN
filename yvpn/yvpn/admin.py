import typer

from yvpn import api_calls
from yvpn.config import console

app = typer.Typer(no_args_is_help=True,
                  add_completion=False)


@app.command()
def create(funds: int, expiration: int, admin: bool = typer.Argument(False)):
    """CREATE a new token"""
    new_token = api_calls.create_token(funds, expiration, admin)
    console.print(new_token)


@app.command()
def get():
    """GET all tokens"""
    tokens = api_calls.get_all_tokens()
    console.print(tokens)


@app.command()
def delete(token: str):
    """DELETE a token"""
    api_calls.delete_token(token)


if __name__ == "__main__":
    app()
