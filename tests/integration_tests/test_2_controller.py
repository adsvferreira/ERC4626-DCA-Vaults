import pytest
from typing import List
from brownie import StrategyWorker, Controller, TreasuryVault, exceptions, Contract
from helpers import get_account_from_pk, check_network_is_mainnet_fork, get_strategy_vault, perc_mul_contracts_simulate

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
    wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet2)
    total_wallet_buy_amount_in_deposit_asset = sum(wallet_buy_amounts)
    treasury_fee_on_balance_update_in_deposit_asset = sum(
        [
            perc_mul_contracts_simulate(wallet_buy_amount, configs["creator_percentage_fee_on_deposit"])
            for wallet_buy_amount in wallet_buy_amounts
        ]
    )
    initial_vault_last_update_timestamp = strategy_vault.lastUpdate()
    min_buy_assets_amounts_out = __get_min_buy_assets_amounts_out(configs, dex_router, wallet_buy_amounts)
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
        == total_wallet_buy_amount_in_deposit_asset
    )
    assert (
        initial_depositor_vault_lp_balance - final_depositor_vault_lp_balance
        == total_wallet_buy_amount_in_deposit_asset
    )  # Ratio 1:1 lp token/ underlying token
    assert (
        initial_vault_lp_total_suppy - final_vault_lp_total_suppy == total_wallet_buy_amount_in_deposit_asset
    )  # Ratio 1:1 lp token/ underlying token
    assert (
        final_treasury_vault_balance_of_deposit_asset - initial_treasury_vault_balance_of_deposit_asset
        == treasury_fee_on_balance_update_in_deposit_asset
    )
    assert initial_vault_last_update_timestamp == 0
    assert final_vault_last_update_timestamp == tx.timestamp
    for i in range(strategy_vault.buyAssetsLength()):
        assert (
            final_depositor_balances_of_buy_assets[i] - initial_depositor_balances_of_buy_assets[i]
        ) >= min_buy_assets_amounts_out[i] * (1 - (configs["max_slippage_perc"] / 10_000))


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


################################ Helper Functions ################################


def __get_min_buy_assets_amounts_out(configs: dict, dex_router: Contract, wallet_buy_amounts: List[int]) -> List[int]:
    return [
        __get_min_amount_out(buy_token_address, buy_amount, configs, dex_router)
        for buy_token_address, buy_amount in zip(
            configs["buy_token_addresses"],
            wallet_buy_amounts,
        )
    ]


def __get_min_amount_out(buy_token_address: str, buy_amount: int, configs: dict, dex_router: Contract) -> int:
    buy_amount_after_fee = __get_buy_amount_after_fee(buy_amount, configs["treasury_percentage_fee_on_balance_update"])
    path = __get_path(buy_token_address, configs["deposit_token_address"], configs["dex_main_token_address"])
    amounts_out = dex_router.getAmountsOut(buy_amount_after_fee, path)
    return amounts_out[-1]


def __get_buy_amount_after_fee(buy_amount: int, perc_fee: int) -> int:
    one_hunderd_percent_minus_perc_fee = 10_000 - perc_fee
    return perc_mul_contracts_simulate(buy_amount, one_hunderd_percent_minus_perc_fee)


def __get_path(buy_token_address: str, deposit_token_address: str, dex_main_token_address: str) -> List[str]:
    if buy_token_address != dex_main_token_address and deposit_token_address != dex_main_token_address:
        return [deposit_token_address, dex_main_token_address, buy_token_address]
    return [deposit_token_address, buy_token_address]
