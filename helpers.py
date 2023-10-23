import pytest
from typing import Any
from math import floor
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

def encode_custom_error(contract_, err_name: str, params: list[Any]) -> str:

    contract_abi = contract_.abi

    for error in [abi for abi in contract_abi if abi["type"] == "error"]:
        # Get error signature components
        name = error["name"]
        data_types = [collapse_if_tuple(abi_input) for abi_input in error.get("inputs", [])]
        error_signature_hex = function_abi_to_4byte_selector(error).hex()
 
        if err_name == name:
            encoded_params = ''
            for param in params:
                if(type(param)==str):
                    return('typed error: 0x'+error_signature_hex+param.zfill(66)[2:])
                elif(type(param)==int):
                    val = "{0:#0{1}x}".format(param,66)
                    val = val[2:]
                else:
                    return 'Unsupported type'
                encoded_params = encoded_params + val
            return('typed error: 0x'+error_signature_hex+encoded_params)
        
    return 'error not found'