import pytest
from enum import Enum
from math import floor
from brownie import AutomatedVaultERC4626, AutomatedVaultsFactory, accounts, config, network

NULL_ADDRESS = "0x0000000000000000000000000000000000000000"
CONSOLE_SEPARATOR = "--------------------------------------------------------------------------"


def get_account_from_pk(index: int) -> object:
    return accounts.add(config["wallets"][f"from_key_{index}"])


def check_network_is_mainnet_fork():
    if network.show_active() == "development" or "fork" not in network.show_active():
        pytest.skip("Only for mainnet-fork testing!")


def get_strategy_vault(index: int = 0) -> AutomatedVaultERC4626:
    created_strategy_vault_address = AutomatedVaultsFactory[-1].getVaultAddress(index)
    return AutomatedVaultERC4626.at(created_strategy_vault_address)


def perc_mul_contracts_simulate(value: int, percentage: int) -> int:
    # library PercentageMath - Operations are rounded half up -> + 5_000
    return floor((value * percentage + 5_000) / 10_000)


class RoundingMethod(Enum):
    FLOOR = "FLOOT"
    CEIL = "CEIL"


def convert_shares_to_assets(
    shares: int, total_shares: int, total_assets: int, rounding_method: RoundingMethod = RoundingMethod.FLOOR
) -> int:
    return mul_div_simulate(shares, total_assets + 1, total_shares + 10 ** (18), rounding_method)


def convert_assets_to_shares(
    assets: int, total_shares: int, total_assets: int, rounding_method: RoundingMethod = RoundingMethod.FLOOR
) -> int:
    return mul_div_simulate(assets, total_shares + 10 ** (18), total_assets + 1, rounding_method)


def mul_div_simulate(a: int, b: int, denominator: int, rounding_method: RoundingMethod) -> int:
    if a == 0 or b == 0:
        return 0
    # Check for potential overflow during multiplication
    if a > (2**256 - 1) // b:
        raise OverflowError("Multiplication overflow")
    product = a * b
    floor_result = product // denominator
    result = floor_result if rounding_method == RoundingMethod.FLOOR else floor_result + 1
    return result
