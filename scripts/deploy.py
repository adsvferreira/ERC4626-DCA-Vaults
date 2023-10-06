from brownie import config, network
from helpers import get_account_from_pk
from brownie import (
    Contract,
    Resolver,
    Controller,
    TreasuryVault,
    StrategyWorker,
    StrategyManager,
    PriceFeedsDataConsumer,
    AutomatedVaultsFactory,
)

CONSOLE_SEPARATOR = "--------------------------------------------------------------------------"


def main():
    # NETWORK
    print(CONSOLE_SEPARATOR)
    print("CURRENT NETWORK: ", network.show_active())
    print(CONSOLE_SEPARATOR)
    dev_wallet = get_account_from_pk(1)
    print(f"WALLET USED FOR DEPLOYMENT: {dev_wallet.address}")
    dex_router_address = config["networks"][network.show_active()]["dex_router_address"]
    dex_factory_address = config["networks"][network.show_active()]["dex_factory_address"]
    dex_main_token_address = config["networks"][network.show_active()]["dex_main_token_address"]
    native_token_data_feed_address = config["networks"][network.show_active()]["native_token_data_feed_address"]
    verify_flag = config["networks"][network.show_active()]["verify"]

    # SETUP
    treasury_fixed_fee_on_vault_creation = 100_000_000_000_000  # 0.001 ETH
    creator_percentage_fee_on_deposit = 25  # 0.25%
    treasury_percentage_fee_on_balance_update = 25  # 0.25%

    print(CONSOLE_SEPARATOR)
    print("TREASURY VAULT DEPLOYMENT:")
    treasury_vault = deploy_treasury_vault(dev_wallet, verify_flag)
    treasury_address = treasury_vault.address

    print(CONSOLE_SEPARATOR)
    print("CONTROLLER DEPLOYMENT:")
    controller = deploy_controller(dev_wallet, verify_flag)
    controller_address = controller.address

    print(CONSOLE_SEPARATOR)
    print("STRATEGY WORKER DEPLOYMENT:")
    strategy_worker = deploy_strategy_worker(
        dev_wallet,
        verify_flag,
        dex_router_address,
        dex_main_token_address,
        controller_address,
    )
    strategy_worker_address = strategy_worker.address

    print(CONSOLE_SEPARATOR)
    print("PRICE FEEDS DATA CONSUMER DEPLOYMENT:")
    price_feeds_data_consumer = deploy_price_feeds_data_consumer(
        dev_wallet, verify_flag, native_token_data_feed_address
    )
    price_feeds_data_consumer_address = price_feeds_data_consumer.address

    print(CONSOLE_SEPARATOR)
    print("STRATEGY MANAGER DEPLOYMENT:")
    strategy_manager = deploy_strategy_manager(dev_wallet, verify_flag, price_feeds_data_consumer_address)
    strategy_manager_address = strategy_manager.address

    print(CONSOLE_SEPARATOR)
    print("STRATEGY VAULTS FACTORY DEPLOYMENT:")
    automated_vaults_factory = deploy_automated_vaults_factory(
        dev_wallet,
        verify_flag,
        dex_factory_address,
        dex_main_token_address,
        treasury_address,
        strategy_manager_address,
        treasury_fixed_fee_on_vault_creation,
        creator_percentage_fee_on_deposit,
        treasury_percentage_fee_on_balance_update,
    )
    automated_vaults_factory_address = automated_vaults_factory.address

    print(CONSOLE_SEPARATOR)
    print("RESOLVER DEPLOYMENT:")
    deploy_resolver(dev_wallet, verify_flag, automated_vaults_factory_address, strategy_worker_address)


def deploy_treasury_vault(wallet_address: str, verify_flag: bool) -> Contract:
    TreasuryVault.deploy({"from": wallet_address}, publish_source=verify_flag)
    return TreasuryVault[-1]


def deploy_controller(wallet_address: str, verify_flag: bool) -> Contract:
    Controller.deploy({"from": wallet_address}, publish_source=verify_flag)
    return Controller[-1]


def deploy_strategy_worker(
    wallet_address: str,
    verify_flag: bool,
    dex_router_address: str,
    dex_main_token_address: str,
    controller_address: str,
) -> Contract:
    StrategyWorker.deploy(
        dex_router_address,
        dex_main_token_address,
        controller_address,
        {"from": wallet_address},
        publish_source=verify_flag,
    )
    return StrategyWorker[-1]


def deploy_price_feeds_data_consumer(
    wallet_address: str, verify_flag: bool, native_token_data_feed_address: str
) -> Contract:
    PriceFeedsDataConsumer.deploy(native_token_data_feed_address, {"from": wallet_address}, publish_source=verify_flag)
    return PriceFeedsDataConsumer[-1]


def deploy_strategy_manager(wallet_address: str, verify_flag: bool, price_feeds_data_consumer_address: str) -> Contract:
    StrategyManager.deploy(price_feeds_data_consumer_address, {"from": wallet_address}, publish_source=verify_flag)
    return StrategyManager[-1]


def deploy_automated_vaults_factory(
    wallet_address: str,
    verify_flag: bool,
    dex_factory_address: str,
    dex_main_token_address: str,
    treasury_address: str,
    strategy_manager_address: str,
    treasury_fixed_fee_on_vault_creation: int,
    creator_percentage_fee_on_deposit: int,
    treasury_percentage_fee_on_balance_update: int,
) -> Contract:
    AutomatedVaultsFactory.deploy(
        dex_factory_address,
        dex_main_token_address,
        treasury_address,
        strategy_manager_address,
        treasury_fixed_fee_on_vault_creation,
        creator_percentage_fee_on_deposit,
        treasury_percentage_fee_on_balance_update,
        {"from": wallet_address},
        publish_source=verify_flag,
    )
    return AutomatedVaultsFactory[-1]


def deploy_resolver(
    wallet_address: str, verify_flag: bool, automated_vaults_factory_address: str, strategy_worker_address: str
) -> Contract:
    Resolver.deploy(
        automated_vaults_factory_address,
        strategy_worker_address,
        {"from": wallet_address},
        publish_source=verify_flag,
    )
    return Resolver[-1]


"""

usdce_address = "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8"
weth_address = "0x82af49447d8a07e3bd95bd0d56f35241523fbab1"
arb_address = "0x912ce59144191c1204e64559fe8253a0e49e6548"
usdce_data_feed_address= "0x50834f3163758fcc1df9973b6e91f0f0f0434ad3"
weth_data_feed_address= "0x639fe6ab55c921f74e7fac1ee960c0b6293ba612"
arb_data_feed_address = "0xb2a824043730fe05f3da2efafa1cbbe83fa548d6"
usdce_decimals = 6
weth_decimals = 18
arb_decimals = 18
usdce_whitelisted_deposit_asset = (usdce_address, 0, usdce_data_feed_address, True)
weth_whitelisted_deposit_asset = (weth_address, 0, weth_data_feed_address, True)
arb_whitelisted_deposit_asset = (arb_address, 0, arb_data_feed_address, True)
buy_percentages = [833]
buy_frequency = 0
treasury_percentage_fee_on_balance_update = 300

strategy_manager.simulateMinDepositValue(usdce_whitelisted_deposit_asset, buy_percentages, buy_frequency, treasury_percentage_fee_on_balance_update, usdce_decimals)

strategy_manager.simulateMinDepositValue(weth_whitelisted_deposit_asset, buy_percentages, buy_frequency, treasury_percentage_fee_on_balance_update, weth_decimals)

strategy_manager.simulateMinDepositValue(arb_whitelisted_deposit_asset, buy_percentages, buy_frequency, treasury_percentage_fee_on_balance_update, arb_decimals)

"""
