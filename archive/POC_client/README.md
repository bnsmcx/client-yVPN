# Client

The client is a simple command line tool that can request the creation or destruction of VPN endpoints.

When the command is run it should check that wireguard is installed and the user's token is set as an environment variable.  Display helpful error messages if not.

## It consists of the following subcommands:

### `connect`

- Triggers the call to the command and control server to create a new endpoint
- Optional `location` argument to specify the geographic location where the new endpoint should be created
- After successful response from the command and control server, automatically initiate key exchange with the endpoint
- After successful key exchange automatically populate required fields in the returned `wg0.conf` file and store it
- Activate the wg tunnel

### `disconnect`

- Deactivate the wg connection and tell the command and control server to kill the endpoint

