import pytest
from math import ceil
from brownie import StrategyWorker, Controller, TreasuryVault, exceptions
from helpers import get_account_from_pk, check_network_is_mainnet_fork, get_strategy_vault

dev_wallet = get_account_from_pk(1)
dev_wallet2 = get_account_from_pk(2)

DEV_WALLET_VAULT_LP_TOKEN_ALLOWANCE_TO_WORKER_AMOUNT = 9_999_999_999_999_999_999

################################ Contract Actions ################################


def test_trigger_strategy_action_by_owner_address(configs, deposit_token, buy_tokens, dex_router):
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    strategy_worker_address = StrategyWorker[-1].address
    strategy_vault = get_strategy_vault()
    strategy_vault_address = strategy_vault.address
    treasury_vault_address = TreasuryVault[-1].address
    initial_vault_balance_of_deposit_asset = deposit_token.balanceOf(strategy_vault_address)
    initial_depositor_vault_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    initial_depositor_balances_of_buy_assets = [buy_token.balanceOf(dev_wallet2) for buy_token in buy_tokens]
    initial_vault_lp_total_suppy = strategy_vault.totalSupply()
    initial_treasury_vault_balance_of_deposit_asset = deposit_token.balanceOf(treasury_vault_address)
    total_buy_amount_in_deposit_asset = sum([buy_amount for buy_amount in configs["buy_amounts"]])
    treasury_fee_on_balance_update_perc = (
        configs["creator_percentage_fee_on_deposit"] + 0.5
    ) / 10_000  # library PercentageMath - Operations are rounded half up
    treasury_fee_on_balance_update_in_deposit_asset = ceil(
        total_buy_amount_in_deposit_asset * treasury_fee_on_balance_update_perc
    )
    initial_vault_last_update_timestamp = strategy_vault.lastUpdate()
    # Act
    strategy_vault.approve(
        strategy_worker_address, DEV_WALLET_VAULT_LP_TOKEN_ALLOWANCE_TO_WORKER_AMOUNT, {"from": dev_wallet2}
    )
    tx = controller.triggerStrategyAction(
        strategy_worker_address, strategy_vault_address, dev_wallet2, {"from": dev_wallet}
    )
    final_vault_balance_of_deposit_asset = deposit_token.balanceOf(strategy_vault_address)
    final_depositor_vault_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    final_depositor_balances_of_buy_assets = [buy_token.balanceOf(dev_wallet2) for buy_token in buy_tokens]
    final_vault_lp_total_suppy = strategy_vault.totalSupply()
    final_treasury_vault_balance_of_deposit_asset = deposit_token.balanceOf(treasury_vault_address)
    final_vault_last_update_timestamp = strategy_vault.lastUpdate()
    # Assert
    assert (
        initial_vault_balance_of_deposit_asset - final_vault_balance_of_deposit_asset
        == total_buy_amount_in_deposit_asset
    )
    assert (
        initial_depositor_vault_lp_balance - final_depositor_vault_lp_balance == total_buy_amount_in_deposit_asset
    )  # Ratio 1:1 lp token/ underlying token
    assert (
        initial_vault_lp_total_suppy - final_vault_lp_total_suppy == total_buy_amount_in_deposit_asset
    )  # Ratio 1:1 lp token/ underlying token
    assert (
        final_treasury_vault_balance_of_deposit_asset - initial_treasury_vault_balance_of_deposit_asset
        == treasury_fee_on_balance_update_in_deposit_asset
    )
    assert initial_vault_last_update_timestamp == 0
    assert final_vault_last_update_timestamp == tx.timestamp
    # Assert final_depositor_balances_of_buy_assets > dexRouter.amountOutMin


################################ Contract Validations ################################


def test_trigger_strategy_action_by_non_owner_address():
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    strategy_worker_address = StrategyWorker[-1].address
    strategy_vault = get_strategy_vault()
    strategy_vault_address = strategy_vault.address
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        controller.triggerStrategyAction(
            strategy_worker_address, strategy_vault_address, dev_wallet2, {"from": dev_wallet2}
        )


def test_trigger_strategy_action_by_owner_address_for_insufficient_lp_balance_wallet():
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    strategy_worker_address = StrategyWorker[-1].address
    strategy_vault = get_strategy_vault()
    strategy_vault_address = strategy_vault.address
    # Act / Assert
    strategy_vault.approve(
        strategy_worker_address, DEV_WALLET_VAULT_LP_TOKEN_ALLOWANCE_TO_WORKER_AMOUNT, {"from": dev_wallet}
    )
    # dev_wallet withdrew the full vault lp balance in a previous test: "test_total_withdraw" and received some dust
    # amount in "test_balance_of_creator_without_deposit_after_another_wallet_deposit".
    # Thus, at this point, shoudn't have enough balance to cover total_buy_amount_in_deposit_asset
    with pytest.raises(exceptions.VirtualMachineError):
        controller.triggerStrategyAction(
            strategy_worker_address, strategy_vault_address, dev_wallet, {"from": dev_wallet}
        )


def test_trigger_strategy_action_by_owner_address_for_insufficient_lp_allowance_wallet():
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    strategy_worker_address = StrategyWorker[-1].address
    strategy_vault = get_strategy_vault()
    strategy_vault_address = strategy_vault.address
    # Act / Assert
    strategy_vault.approve(strategy_worker_address, 0, {"from": dev_wallet2})
    with pytest.raises(exceptions.VirtualMachineError):
        controller.triggerStrategyAction(
            strategy_worker_address, strategy_vault_address, dev_wallet2, {"from": dev_wallet}
        )
