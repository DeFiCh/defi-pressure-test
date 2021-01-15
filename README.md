# defi-pressure-test
Automatically feed transactions to test the defichain

# Running

- In a system with python3 and pip3 installed, install dependencies: `pip3 install -r requirements.txt`
- Create your configuration file.
- Create config file to say, `./config.toml` (See `config.example.toml` for example)
- Run `python3 main.py --config=config.toml --repeat=5`
- `Repeat = 5` means send a batch of transactions to blockchain every 5 seconds.

You'll have to change at least the following fields in an example config file:
- [DFI.RPC] - set your DeFi daemon RPC credentials
- [TXN.ADDR] - set the test addresses, tokens and liquidity pool
- [TXN.TYPE]- set what types of transactions need to be feed to the blockchain

# Docker
- Make sure have a config file as given above.
- Run command `docker-compose build` to build the docker images.
- Run command `docker run --network="host" defi-pressure-test_main` to run the service as docker.