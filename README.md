# Celo trader

An [Olas](https://olas.network/) agent that makes transactions on the [Celo](https://celo.org/) network.

## System requirements

- Python `>=3.10`
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

## Run you own agent

### Get the code

1. Clone this repo:

    ```git clone git@github.com:valory-xyz/celo-trader.git```

2. Create the virtual environment:

    ```
    cd celo-trader
    poetry shell
    poetry install
    ```

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

2. Deploy a [Safe on Celo](https://app.safe.global/welcome) and set your agent address as one of the signers.

3. Fund both your agent and Safe with a small amount of Celo, i.e. $0.05 each.


### Run the service

1. Make a copy of the env file:

    ```cp sample.env .env```

2. Fill in the required environment variables in .env. You'll need a Ethereum RPC even if the service runs on Celo. These variables are: `ALL_PARTICIPANTS`, `ETHEREUM_LEDGER_RPC` and `SAFE_CONTRACT_ADDRESS`

3. Run the service:

    ```bash run_service.sh```

4. Look at the service logs:

    ```docker logs -f celotrader_abci_0```

5. Make a transfer request. On another terminal:

    ```make transfer_request```

    or make a custom transfer request:

    ```curl -X POST http://localhost:8000/request -H "Content-Type: application/json" -d '{"prompt":"Transfer 1 wei to 0x8D7102ce2d35a409535285252599c149FBeABB73"}'```


## Extend the agent (advanced)

To extend agents, it is useful to first understand their [architecture](https://docs.autonolas.network/open-autonomy/get_started/what_is_an_agent_service/#architecture) and the [development process](https://docs.autonolas.network/open-autonomy/guides/overview_of_the_development_process/).

After you feel comfortable with running agents and their architecture, think about a useful addition or modification for the Celo Trader. For example: modify the agent and the mech tool to perform swaps. The high level steps would be:

1. Using the [prepare_tx](https://github.com/valory-xyz/mech/blob/main/packages/valory/customs/prepare_tx/prepare_tx.py) mech tool as template, create a new mech tool that prepares a swap transaction given a pair of tokens and the amount to swap.

2. Configure your [TOOL env](https://github.com/valory-xyz/celo-trader/blob/main/sample.env#L9) so the agent uses your new tool

3. Modify the agent's [process_next_mech_response](https://github.com/valory-xyz/celo-trader/blob/main/packages/valory/skills/celo_trader_abci/behaviours.py#L207) method in order to get the correct data from the new tool.

4. Update the [transaction preparation on the agent](https://github.com/valory-xyz/celo-trader/blob/main/packages/valory/skills/celo_trader_abci/behaviours.py#L173) so, instead of a simple transfer, it uses the data received in the previous step to make a call to Uniswap. [Here's an example on how to make a contract call](https://github.com/valory-xyz/price-oracle/blob/main/packages/valory/skills/price_estimation_abci/behaviours.py#L361). Since agents communicate with contracts through the contract_api, you will need to create a [contract package](https://open-aea.docs.autonolas.tech/creating-contracts/) (essentially a contract wrapper) for Uniswap that implements a single method to swap. [Here's a contract method for reference](https://github.com/valory-xyz/price-oracle/blob/main/packages/valory/contracts/offchain_aggregator/contract.py#L197).

The [trader agent](https://github.com/valory-xyz/trader) might be a good example to understand how to make transactions using an agent. There's a easy to follow [quickstart for this agent](https://github.com/valory-xyz/trader-quickstart) that anyone can use to run the trader.