# Celo trader

An [Olas](https://olas.network/) agent that makes transactions on the [Celo](https://celo.org/) network.

## System requirements

- Python `>=3.8`
- [Tendermint](https://docs.tendermint.com/v0.34/introduction/install.html) `==0.34.19`
- [IPFS node](https://docs.ipfs.io/install/command-line/#official-distributions) `==0.6.0`
- [Pip](https://pip.pypa.io/en/stable/installation/)
- [Poetry](https://python-poetry.org/)
- [Docker Engine](https://docs.docker.com/engine/install/)
- [Docker Compose](https://docs.docker.com/compose/install/)

Alternatively, you can fetch this docker image with the relevant requirements satisfied:

> **_NOTE:_**  Tendermint and IPFS dependencies are missing from the image at the moment.

```bash
docker pull valory/open-autonomy-user:latest
docker container run -it valory/open-autonomy-user:latest
```

## Run you own instance

### Get the code

1. Clone this repo:

    ```git clone git@github.com:valory-xyz/celo-trader.git```

2. Create the virtual environment:

    ```poetry shell && poetry install```

3. Sync packages:

    ```autonomy packages sync --update-packages```

### Prepare the data

1. Prepare a keys.json file containing wallet address and the private key for each of the agents. This is an example:

```
[
    {
        "address": "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
        "private_key": "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a"
    }
]
```

2. Deploy a [Safe on Gnosis](https://app.safe.global/welcome) (it's free) and set your agent address as one of the signers.


### Run the service

1. Make a copy of the env file:

    ```cp sample.env .env```

2. Fill in the required environment variables in .env. Fill in the variables inside .env. You'll need some RPCs for Ethereum and Gnosis chain.

3. Run the service:

    ```bash run_service.sh```

4. Make a transfer request. On another terminal:

    ```curl -X POST http://localhost:8000/request -H "Content-Type: application/json" -d '{"prompt":"Transfer 1 wei to 0x8D7102ce2d35a409535285252599c149FBeABB73"}'```