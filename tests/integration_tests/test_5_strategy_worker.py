from eth_abi import abi 
from brownie import StrategyWorker, exceptions, reverts, web3

from helpers import (
    get_strategy_vault,
    encode_custom_error, 
    get_account_from_pk, 
    check_network_is_mainnet_fork,
    )

dev_wallet = get_account_from_pk(1)

CONTROLLER_CALLER_BYTES_ROLE = web3.keccak(text="CONTROLLER")


def test_execute_strategy_action_by_non_controller_address():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_worker = StrategyWorker[-1]
    strategy_vault_address = get_strategy_vault().address
    # Act / Assert
    with reverts(encode_custom_error(StrategyWorker, "AccessControlUnauthorizedAccount", []) + abi.encode(["address", "bytes32"], [dev_wallet.address, CONTROLLER_CALLER_BYTES_ROLE]).hex()):
        strategy_worker.executeStrategyAction(strategy_vault_address, dev_wallet, {"from": dev_wallet})
