from brownie import StrategyWorker, reverts, web3

from helpers import (
    get_strategy_vault,
    get_account_from_pk,
    encode_custom_error_data,
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
    with reverts(
        encode_custom_error_data(
            StrategyWorker,
            "AccessControlUnauthorizedAccount",
            ["address", "bytes32"],
            [dev_wallet.address, CONTROLLER_CALLER_BYTES_ROLE],
        )
    ):
        strategy_worker.executeStrategyAction(strategy_vault_address, dev_wallet, {"from": dev_wallet})
