# yvpn
> A CLI client to manage YOUR vpn.

## Overview

The yvpn tool is a command line client that allows users to manage VPN endpoints by communicating with the yourvpn.info service.  

Users can create, use, and destroy VPN endpoints at will.  These endpoints are Virtual Private Servers that are created for the exclusive use of the user unlike other VPN providers where thousands of users share a single endpoint.

This tool is meant to be extensible.  Beneath the hood SSH is used for the initial wireguard key exchange and future releases will allow users to quickly drop directly into a shell on the remote machine, perform file transfers, or remotely execute scripts.  

This is not just a a tool for managing your VPN needs, but also a powerful resource for quickly deploying on demand services limited only by your creativity.

## Installation

The quickest way to get up and running is to install the tool from pip:

`pip3 install yvpn`

You will need wireguard:

(https://www.wireguard.com/install/)(https://www.wireguard.com/install/)

You need to set two environment variables:

1. The server url:
	`URL_yVPN="https://yourvpn.info"`

2. Your token:
	`TOKEN_yVPN="<token>"`

## Where to get tokens

Right now yvpn is in closed alpha.  Tokens are available by invitation only.

## What even is a token?  Like an account?

No, we do not and will never offer accounts.  Privacy is a core principal and we figure the best way to preserve user's privacy is to simply store zero user information.  That's where Tokens come in.

Think of a token as a sort of prepaid calling card.  Remember those good old days?  Where you'd buy a calling card with however many minutes preloaded and then you had to call a 1-800 number from a payphone and enter the little code beneath the scratch off material?  That's what our token model will be.  

One day, once we're ready for a beta, there will be a simple storefront where you can buy a token preloaded with some amount of credit and off you go.

## How will billing work then?

There will be no billing as in no invoicing.  Your token's fund balance will be debited based directly on usage.  If you don't have any endpoints running, you won't pay anything. 

## Overview of commands

### `yvpn clean`

Destroys all of your endpoints and refreshes your wireguard keys.

### `yvpn connect`

Connect to an endpoint.  You can pass the name or number of the endpoint to connect to a specific one, i.e. `yvpn connect 3`, or automatically connect to the first one on the list without.

### `yvpn create`

Create a new endpoint.  You can optionally specify a specific datacenter, `yvpn create lon1`, see `yvpn datacenters` below, or create a new endpoint in a randomly selected datacenter by omitting the final argument.

### `yvpn datacenters`

Displays a list of the currently available datacenters.  

### `yvpn destroy <num>`

Destroy the specified endpoint.

### `yvpn disconnect`

Disconnect from the active endpoint.

### `yvpn status`

Display a table of your endpoints with a number, name, location, and creation timestamp.  Also displays your token's balance and expected depletion date at current usage.

