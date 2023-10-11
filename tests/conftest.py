import pytest
from typing import List
from brownie import config, network, Contract
from helpers import check_network_is_mainnet_fork
from docs.abis import erc20_abi, univ2_dex_router_abi


@pytest.fixture()
def configs() -> dict:
    check_network_is_mainnet_fork()
    active_network_configs = config["networks"][network.show_active()]
    protocol_params = config["protocol-params"]
    strategy_params = config["strategy-params"]
    return {
        "dex_main_token_address": active_network_configs["dex_main_token_address"],
        "dex_router_address": active_network_configs["dex_router_address"],
        "dex_factory_address": active_network_configs["dex_factory_address"],
        "native_token_data_feed_address": active_network_configs["native_token_data_feed_address"],
        "deposit_token_address": active_network_configs["deposit_token_address"],
        "whitelisted-deposit-assets": active_network_configs["whitelisted-deposit-assets"],
        "not-whitelisted-token-address-example": active_network_configs["not-whitelisted-token-address-example"],
        "buy_token_addresses": active_network_configs["buy_token_addresses"],
        "vault_name": active_network_configs["vault_name"],
        "vault_symbol": active_network_configs["vault_symbol"],
        "treasury_fixed_fee_on_vault_creation": protocol_params["treasury_fixed_fee_on_vault_creation"],
        "creator_percentage_fee_on_deposit": protocol_params["creator_percentage_fee_on_deposit"],
        "treasury_percentage_fee_on_balance_update": protocol_params["treasury_percentage_fee_on_balance_update"],
        "max_slippage_perc": protocol_params["max_slippage_perc"],
        "buy_percentages": strategy_params["buy_percentages"],
        "buy_frequency": strategy_params["buy_frequency"],
        "token_not_paired_with_weth_address": active_network_configs["token_not_paired_with_weth_address"],
        "too_many_buy_token_addresses": active_network_configs["too_many_buy_token_addresses"],
    }


@pytest.fixture()
def deposit_token() -> Contract:
    return Contract.from_abi(
        "ERC20",
        config["networks"][network.show_active()]["deposit_token_address"],
        erc20_abi,
    )


@pytest.fixture()
def buy_tokens() -> List[Contract]:
    return [
        Contract.from_abi("ERC20", buy_token_address, erc20_abi)
        for buy_token_address in config["networks"][network.show_active()]["buy_token_addresses"]
    ]


@pytest.fixture()
def dex_router() -> Contract:
    return Contract.from_abi(
        "ROUTER",
        config["networks"][network.show_active()]["dex_router_address"],
        univ2_dex_router_abi,
    )
