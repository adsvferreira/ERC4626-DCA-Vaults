from brownie import config, network
from helpers import get_account_from_pk
from brownie import (
    AutomatedVaultsFactory,
    TreasuryVault,
    StrategyWorker,
    Controller,
    Contract,
)

CONSOLE_SEPARATOR = (
    "--------------------------------------------------------------------------"
)


def main():
    # NETWORK
    print(CONSOLE_SEPARATOR)
    print("CURRENT NETWORK: ", network.show_active())
    print(CONSOLE_SEPARATOR)
    dev_wallet = get_account_from_pk(1)
    print(f"WALLET USED FOR DEPLOYMENT: {dev_wallet.address}")
    dex_router_address = config["networks"][network.show_active()]["dex_router_address"]
    dex_factory_address = config["networks"][network.show_active()][
        "dex_factory_address"
    ]
    dex_main_token_address = config["networks"][network.show_active()][
        "dex_main_token_address"
    ]
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
    deploy_strategy_worker(
        dev_wallet,
        verify_flag,
        dex_router_address,
        dex_main_token_address,
        controller_address,
    )

    print(CONSOLE_SEPARATOR)
    print("STRATEGY VAULTS FACTORY DEPLOYMENT:")
    deploy_automated_vaults_factory(
        dev_wallet,
        verify_flag,
        dex_factory_address,
        dex_main_token_address,
        treasury_address,
        treasury_fixed_fee_on_vault_creation,
        creator_percentage_fee_on_deposit,
        treasury_percentage_fee_on_balance_update,
    )


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


def deploy_automated_vaults_factory(
    wallet_address: str,
    verify_flag: bool,
    dex_factory_address: str,
    dex_main_token_address: str,
    treasury_address: str,
    treasury_fixed_fee_on_vault_creation: int,
    creator_percentage_fee_on_deposit: int,
    treasury_percentage_fee_on_balance_update: int,
) -> Contract:
    AutomatedVaultsFactory.deploy(
        dex_factory_address,
        dex_main_token_address,
        treasury_address,
        treasury_fixed_fee_on_vault_creation,
        creator_percentage_fee_on_deposit,
        treasury_percentage_fee_on_balance_update,
        {"from": wallet_address},
        publish_source=verify_flag,
    )
    return AutomatedVaultsFactory[-1]
