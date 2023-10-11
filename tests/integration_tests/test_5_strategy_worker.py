import pytest
from brownie import StrategyWorker, exceptions
from helpers import get_account_from_pk, check_network_is_mainnet_fork, get_strategy_vault

dev_wallet = get_account_from_pk(1)


def test_execute_strategy_action_by_non_controller_address():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_worker = StrategyWorker[-1]
    strategy_vault_address = get_strategy_vault().address
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        strategy_worker.executeStrategyAction(strategy_vault_address, dev_wallet, {"from": dev_wallet})
