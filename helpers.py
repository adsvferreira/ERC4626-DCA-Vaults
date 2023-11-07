import pytest
from enum import Enum
from typing import Any, List
from math import floor
from eth_abi import abi
from eth_utils.abi import function_abi_to_4byte_selector, collapse_if_tuple
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
    FLOOR = "FLOOR"
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


def encode_custom_error(contract, err_name: str, params: List[Any]) -> str:
    contract_abi = contract.abi

    for error in [abi for abi in contract_abi if abi["type"] == "error"]:
        # Get error signature components
        name = error["name"]
        data_types = [collapse_if_tuple(abi_input) for abi_input in error.get("inputs", [])]
        error_signature_hex = function_abi_to_4byte_selector(error).hex()

        if err_name == name:
            encoded_params = ""
            for param in params:
                if type(param) == str:
                    return "typed error: 0x" + error_signature_hex + param.zfill(66)[2:]
                elif type(param) == int:
                    val = "{0:#0{1}x}".format(param, 66)
                    val = val[2:]
                else:
                    return "Unsupported type"
                encoded_params = encoded_params + val
            return "typed error: 0x" + error_signature_hex + encoded_params

    return "error not found"


def encode_custom_error_data(contract, err_name: str, param_types: List[str], params: List[str]):
    return encode_custom_error(contract, err_name, []) + abi.encode(param_types, params).hex()
