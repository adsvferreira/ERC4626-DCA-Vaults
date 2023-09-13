import pytest
from brownie import AutomatedVaultERC4626, AutomatedVaultsFactory, accounts, config, network


def get_account_from_pk(index: int) -> object:
    return accounts.add(config["wallets"][f"from_key_{index}"])


def check_network_is_mainnet_fork():
    if network.show_active() == "development" or "fork" not in network.show_active():
        pytest.skip("Only for mainnet-fork testing!")


def get_strategy_vault(index: int = 0) -> AutomatedVaultERC4626:
    created_strategy_vault_address = AutomatedVaultsFactory[-1].allVaults(index)
    return AutomatedVaultERC4626.at(created_strategy_vault_address)
