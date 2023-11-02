from helpers import (
    RoundingMethod,
    get_strategy_vault,
    get_account_from_pk,
    convert_shares_to_assets,
    convert_assets_to_shares,
    perc_mul_contracts_simulate,
    check_network_is_mainnet_fork,
    NULL_ADDRESS,
)
from docs.abis import erc20_abi, univ2_dex_router_abi

dev_wallet = get_account_from_pk(1)
deployer_wallet = get_account_from_pk(2)

deposit_amount = 15_000_000

active_network_configs = config["networks"][network.show_active()]
protocol_params = config["protocol-params"]
strategy_params = config["strategy-params"]

strategy_manager_address = "0xEBF39FB51c23918F2FcbbD0600Bb6dE1546a37C3"
strategy_worker_address = "0x43Cc4744343fC5d44F27f4Ff2d97D18b261aEeC8"
factory_address = "0xF45309A5269a28e4F49Ab3aDd7aAFC70b1362E85"

vaults_factory = AutomatedVaultsFactory.at(factory_address)

active_network_configs = config["networks"][network.show_active()]
protocol_params = config["protocol-params"]
strategy_params = config["strategy-params"]
configs = {
    "dex_main_token_address": active_network_configs["dex_main_token_address"],
    "dex_router_address": active_network_configs["dex_router_address"],
    "dex_factory_address": active_network_configs["dex_factory_address"],
    "native_token_data_feed_address": active_network_configs["native_token_data_feed_address"],
    "deposit_token_address": active_network_configs["deposit_token_address"],
    "whitelisted_deposit_assets": active_network_configs["whitelisted_deposit_assets"],
    "not_whitelisted_token_address_example": active_network_configs["not_whitelisted_token_address_example"],
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


def __get_default_strategy_and_init_vault_params(configs: dict):
    worker_address = StrategyWorker.at(strategy_worker_address).address
    strategy_manager = StrategyManager.at(strategy_manager_address).address
    init_vault_from_factory_params = (
        configs["vault_name"],
        configs["vault_symbol"],
        configs["deposit_token_address"],
        configs["buy_token_addresses"],
    )
    strategy_params = (configs["buy_percentages"], configs["buy_frequency"], worker_address, strategy_manager)
    return strategy_params, init_vault_from_factory_params


(
    strategy_params,
    init_vault_from_factory_params,
) = __get_default_strategy_and_init_vault_params(configs)

deposit_token = Contract.from_abi(
    "ERC20",
    config["networks"][network.show_active()]["deposit_token_address"],
    erc20_abi,
)

# deposit_token.approve(vaults_factory.address, deposit_amount, {"from": dev_wallet})

vault_address = vaults_factory.getBatchVaults(1, 0)[0]
vault = AutomatedVaultERC4626.at(vault_address)

vault.approve(
    "0x43Cc4744343fC5d44F27f4Ff2d97D18b261aEeC8", 999_999_999_999_999_999_999_999_999_999, {"from": dev_wallet}
)

tx = vaults_factory.createVault(
    init_vault_from_factory_params,
    strategy_params,
    deposit_amount,
    {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
)


# wss://arb-mainnet.g.alchemy.com/v2/U_yw98bojySygt6-zxUeDS3R3QNVaJ9e
