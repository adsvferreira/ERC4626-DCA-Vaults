import pytest
from typing import List
from scripts.deploy import deploy_resolver

from helpers import (
    RoundingMethod,
    get_strategy_vault,
    NULL_ADDRESS,
    get_account_from_pk,
    encode_custom_error,
    encode_custom_error_data,
    convert_assets_to_shares,
    perc_mul_contracts_simulate,
    check_network_is_mainnet_fork,
)
from brownie import (
    Contract,
    Resolver,
    Controller,
    TreasuryVault,
    StrategyWorker,
    AutomatedVaultERC4626,
    AutomatedVaultsFactory,
    web3,
    config,
    network,
    reverts,
    exceptions,
)

dev_wallet = get_account_from_pk(1)
dev_wallet2 = get_account_from_pk(2)

DEV_WALLET_VAULT_LP_TOKEN_ALLOWANCE_TO_WORKER_AMOUNT = 999_999_999_999_999_999_999_999_999_999
DEV_WALLET_DEPOSIT_TOKEN_AMOUNT = 20_000

CONTROLLER_CALLER_BYTES_ROLE = web3.keccak(text="CONTROLLER_CALLER")
ENCODER_SEPARATOR = "0000000000000000000000000000000000000000000000000000000000000000"

################################ Contract Actions ################################


def test_resolver_checker_before_controller_first_action():
    check_network_is_mainnet_fork()
    # Arrange
    verify_flag = config["networks"][network.show_active()]["verify"]
    strategy_worker_address = StrategyWorker[-1].address
    automated_vaults_factory_address = AutomatedVaultsFactory[-1].address
    controller = Controller[-1]
    first_deployed_vault_address = AutomatedVaultERC4626[0].address
    expected_decoded_payload = (
        "triggerStrategyAction(address,address,address)",
        [strategy_worker_address, first_deployed_vault_address, dev_wallet.address],
    )
    # Act
    resolver = deploy_resolver(dev_wallet, verify_flag, automated_vaults_factory_address, strategy_worker_address)
    can_exec, payload = resolver.checker()
    decoded_payload = controller.decode_input(payload)
    # Assert
    assert can_exec == True
    assert decoded_payload == expected_decoded_payload


def test_trigger_strategy_action_by_owner_address(configs, deposit_token, buy_tokens, dex_router):
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    strategy_worker_address = StrategyWorker[-1].address
    strategy_vault = get_strategy_vault()
    strategy_vault_address = strategy_vault.address
    treasury_vault_address = TreasuryVault[-1].address
    initial_vault_balance_of_deposit_asset = deposit_token.balanceOf(strategy_vault_address)
    initial_depositor_vault_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_depositor_balances_of_buy_assets = [buy_token.balanceOf(dev_wallet) for buy_token in buy_tokens]
    initial_vault_lp_total_suppy = strategy_vault.totalSupply()
    initial_vault_total_assets = strategy_vault.totalAssets()
    initial_treasury_vault_balance_of_deposit_asset = deposit_token.balanceOf(treasury_vault_address)
    wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet)
    total_wallet_buy_amount_in_deposit_asset = sum(wallet_buy_amounts)
    treasury_fee_on_balance_update_in_deposit_asset = sum(
        [
            perc_mul_contracts_simulate(wallet_buy_amount, configs["treasury_percentage_fee_on_balance_update"])
            for wallet_buy_amount in wallet_buy_amounts
        ]
    )
    initial_wallet_vault_last_updated_timestamp = strategy_vault.lastUpdateOf(dev_wallet)
    min_buy_assets_amounts_out = __get_min_buy_assets_amounts_out(configs, dex_router, wallet_buy_amounts)
    # Act
    strategy_vault.approve(
        strategy_worker_address, DEV_WALLET_VAULT_LP_TOKEN_ALLOWANCE_TO_WORKER_AMOUNT, {"from": dev_wallet}
    )
    tx = controller.triggerStrategyAction(
        strategy_worker_address, strategy_vault_address, dev_wallet, {"from": dev_wallet}
    )
    final_vault_balance_of_deposit_asset = deposit_token.balanceOf(strategy_vault_address)
    final_depositor_vault_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_depositor_balances_of_buy_assets = [buy_token.balanceOf(dev_wallet) for buy_token in buy_tokens]
    final_vault_lp_total_suppy = strategy_vault.totalSupply()
    final_treasury_vault_balance_of_deposit_asset = deposit_token.balanceOf(treasury_vault_address)
    final_wallet_vault_last_updated_timestamp = strategy_vault.lastUpdateOf(dev_wallet)
    # Assert
    assert (
        initial_vault_balance_of_deposit_asset - final_vault_balance_of_deposit_asset
        == total_wallet_buy_amount_in_deposit_asset
    )
    assert initial_depositor_vault_lp_balance - final_depositor_vault_lp_balance == convert_assets_to_shares(
        total_wallet_buy_amount_in_deposit_asset,
        initial_vault_lp_total_suppy,
        initial_vault_total_assets,
        RoundingMethod.CEIL,
    )
    assert initial_vault_lp_total_suppy - final_vault_lp_total_suppy == convert_assets_to_shares(
        total_wallet_buy_amount_in_deposit_asset,
        initial_vault_lp_total_suppy,
        initial_vault_total_assets,
        RoundingMethod.CEIL,
    )
    assert (
        final_treasury_vault_balance_of_deposit_asset - initial_treasury_vault_balance_of_deposit_asset
        == treasury_fee_on_balance_update_in_deposit_asset
    )
    assert initial_wallet_vault_last_updated_timestamp == 0
    assert final_wallet_vault_last_updated_timestamp == tx.timestamp
    for i in range(strategy_vault.buyAssetsLength()):
        assert (
            final_depositor_balances_of_buy_assets[i] - initial_depositor_balances_of_buy_assets[i]
        ) >= min_buy_assets_amounts_out[i] * (1 - (configs["max_slippage_perc"] / 10_000))


def test_resolver_checker_after_controller_first_action():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_worker_address = StrategyWorker[-1].address
    controller = Controller[-1]
    first_deployed_vault_address = get_strategy_vault()
    expected_decoded_payload = (
        "triggerStrategyAction(address,address,address)",
        [strategy_worker_address, first_deployed_vault_address, dev_wallet2.address],
    )
    resolver = Resolver[-1]
    # Act
    can_exec, payload = resolver.checker()
    decoded_payload = controller.decode_input(payload)
    # Assert
    assert can_exec == True
    assert decoded_payload == expected_decoded_payload


def test_resolver_checker_after_controller_update_all_vaults(deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    first_deployed_strategy_vault = get_strategy_vault()
    second_deployed_strategy_vault = get_strategy_vault(1)
    third_deployed_strategy_vault = get_strategy_vault(2)
    first_deployed_strategy_vault_address = first_deployed_strategy_vault.address
    second_deployed_strategy_vault_address = second_deployed_strategy_vault.address
    third_deployed_strategy_vault_address = third_deployed_strategy_vault.address
    strategy_worker_address = StrategyWorker[-1].address
    controller = Controller[-1]
    resolver = Resolver[-1]
    expected_decoded_last_payload = (
        "triggerStrategyAction(address,address,address)",
        [strategy_worker_address, third_deployed_strategy_vault_address, dev_wallet.address],
    )
    # Act
    first_deployed_strategy_vault.approve(
        strategy_worker_address, DEV_WALLET_VAULT_LP_TOKEN_ALLOWANCE_TO_WORKER_AMOUNT, {"from": dev_wallet2}
    )
    second_deployed_strategy_vault.approve(
        strategy_worker_address, DEV_WALLET_VAULT_LP_TOKEN_ALLOWANCE_TO_WORKER_AMOUNT, {"from": dev_wallet}
    )
    controller.triggerStrategyAction(
        strategy_worker_address, first_deployed_strategy_vault_address, dev_wallet2, {"from": dev_wallet}
    )
    controller.triggerStrategyAction(
        strategy_worker_address, second_deployed_strategy_vault_address, dev_wallet, {"from": dev_wallet}
    )
    second_deployed_strategy_vault.approve(
        strategy_worker_address, DEV_WALLET_VAULT_LP_TOKEN_ALLOWANCE_TO_WORKER_AMOUNT, {"from": dev_wallet2}
    )
    controller.triggerStrategyAction(
        strategy_worker_address, second_deployed_strategy_vault_address, dev_wallet2, {"from": dev_wallet}
    )
    third_deployed_strategy_vault.approve(
        strategy_worker_address, DEV_WALLET_VAULT_LP_TOKEN_ALLOWANCE_TO_WORKER_AMOUNT, {"from": dev_wallet}
    )
    controller.triggerStrategyAction(
        strategy_worker_address, third_deployed_strategy_vault_address, dev_wallet, {"from": dev_wallet}
    )
    can_exec, payload = resolver.checker()
    decoded_last_payload = controller.decode_input(payload)
    # Assert
    assert not can_exec
    assert decoded_last_payload == expected_decoded_last_payload


def test_trigger_strategy_action_before_next_valid_timestamp():
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    strategy_worker_address = StrategyWorker[-1].address
    strategy_vault = get_strategy_vault()
    strategy_vault_address = strategy_vault.address
    # Act / Assert
    with reverts(encode_custom_error(StrategyWorker, "UpdateConditionsNotMet", [])):
        controller.triggerStrategyAction(
            strategy_worker_address, strategy_vault_address, dev_wallet2, {"from": dev_wallet}
        )


def test_trigger_strategy_action_by_address_without_controller_role():
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    strategy_worker_address = StrategyWorker[-1].address
    strategy_vault = get_strategy_vault()
    strategy_vault_address = strategy_vault.address
    # Act / Assert
    with reverts(
        encode_custom_error_data(
            Controller,
            "AccessControlUnauthorizedAccount",
            ["address", "bytes32"],
            [dev_wallet2.address, CONTROLLER_CALLER_BYTES_ROLE],
        )
    ):
        controller.triggerStrategyAction(
            strategy_worker_address, strategy_vault_address, dev_wallet2, {"from": dev_wallet2}
        )


def test_add_controller_role_to_address():
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    strategy_worker_address = StrategyWorker[-1].address
    strategy_vault = get_strategy_vault()
    strategy_vault_address = strategy_vault.address
    # Act
    controller.grantRole(CONTROLLER_CALLER_BYTES_ROLE, dev_wallet2, {"from": dev_wallet})
    # Assert
    with reverts(encode_custom_error(StrategyWorker, "UpdateConditionsNotMet", [])):
        controller.triggerStrategyAction(
            strategy_worker_address, strategy_vault_address, dev_wallet2, {"from": dev_wallet2}
        )
    assert controller.hasRole(CONTROLLER_CALLER_BYTES_ROLE, dev_wallet) == True


def test_remove_controller_role_from_address():
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    strategy_worker_address = StrategyWorker[-1].address
    strategy_vault = get_strategy_vault()
    strategy_vault_address = strategy_vault.address
    # Act
    controller.revokeRole(CONTROLLER_CALLER_BYTES_ROLE, dev_wallet2, {"from": dev_wallet})
    # Assert
    with reverts(
        encode_custom_error_data(
            Controller,
            "AccessControlUnauthorizedAccount",
            ["address", "bytes32"],
            [dev_wallet2.address, CONTROLLER_CALLER_BYTES_ROLE],
        )
    ):
        controller.triggerStrategyAction(
            strategy_worker_address, strategy_vault_address, dev_wallet2, {"from": dev_wallet2}
        )
    assert controller.hasRole(CONTROLLER_CALLER_BYTES_ROLE, dev_wallet) == True


################################ Contract Validations ################################


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
    with reverts(encode_custom_error(StrategyWorker, "UpdateConditionsNotMet", [])):
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
    with reverts(encode_custom_error(StrategyWorker, "UpdateConditionsNotMet", [])):
        controller.triggerStrategyAction(
            strategy_worker_address, strategy_vault_address, dev_wallet2, {"from": dev_wallet}
        )


def test_trigger_strategy_action_with_invalid_worker_address():
    controller = Controller[-1]
    invalid_worker_address = config["networks"][network.show_active()]["treasury_address"]
    strategy_vault = get_strategy_vault()
    strategy_vault_address = strategy_vault.address
    # Act / Assert
    strategy_vault.approve(
        invalid_worker_address, DEV_WALLET_VAULT_LP_TOKEN_ALLOWANCE_TO_WORKER_AMOUNT, {"from": dev_wallet2}
    )
    with pytest.raises(exceptions.VirtualMachineError):  # Reverts with empty string
        controller.triggerStrategyAction(
            invalid_worker_address, strategy_vault_address, dev_wallet2, {"from": dev_wallet}
        )


def test_trigger_strategy_action_with_invalid_vault_address():
    controller = Controller[-1]
    strategy_worker_address = StrategyWorker[-1].address
    invalid_vault_address = config["networks"][network.show_active()]["treasury_address"]
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):  # Reverts with empty string
        controller.triggerStrategyAction(
            strategy_worker_address, invalid_vault_address, dev_wallet2, {"from": dev_wallet}
        )


def test_trigger_strategy_action_with_null_depositor_address():
    controller = Controller[-1]
    strategy_worker_address = StrategyWorker[-1].address
    strategy_vault = get_strategy_vault()
    strategy_vault_address = strategy_vault.address
    # Act / Assert
    with reverts(encode_custom_error(StrategyWorker, "ZeroOrNegativeVaultWithdrawAmount", [])):
        controller.triggerStrategyAction(
            strategy_worker_address, strategy_vault_address, NULL_ADDRESS, {"from": dev_wallet}
        )


def test_add_controller_role_to_address_by_non_admin():
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    # Act/Assert
    controller.revokeRole(CONTROLLER_CALLER_BYTES_ROLE, dev_wallet2, {"from": dev_wallet})
    with reverts(
        encode_custom_error_data(StrategyWorker, "AccessControlUnauthorizedAccount", ["address"], [dev_wallet2.address])
        + ENCODER_SEPARATOR
    ):
        controller.grantRole(CONTROLLER_CALLER_BYTES_ROLE, dev_wallet2, {"from": dev_wallet2})
    assert controller.hasRole(CONTROLLER_CALLER_BYTES_ROLE, dev_wallet2) == False


def test_remove_controller_role_from_address_by_non_admin():
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    # Act/Assert
    controller.grantRole(CONTROLLER_CALLER_BYTES_ROLE, dev_wallet2, {"from": dev_wallet})
    with reverts(
        encode_custom_error_data(StrategyWorker, "AccessControlUnauthorizedAccount", ["address"], [dev_wallet2.address])
        + ENCODER_SEPARATOR
    ):
        controller.revokeRole(CONTROLLER_CALLER_BYTES_ROLE, dev_wallet2, {"from": dev_wallet2})
    assert controller.hasRole(CONTROLLER_CALLER_BYTES_ROLE, dev_wallet2) == True


def test_remove_controller_role_from_admin_by_non_admin():
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    # Act/Assert
    with reverts(
        encode_custom_error_data(StrategyWorker, "AccessControlUnauthorizedAccount", ["address"], [dev_wallet2.address])
        + ENCODER_SEPARATOR
    ):
        controller.revokeRole(CONTROLLER_CALLER_BYTES_ROLE, dev_wallet, {"from": dev_wallet2})
    assert controller.hasRole(CONTROLLER_CALLER_BYTES_ROLE, dev_wallet) == True


def test_add_controller_role_to_null_address_by_non_admin():
    check_network_is_mainnet_fork()
    # Arrange
    controller = Controller[-1]
    # Act/Assert
    with reverts(
        encode_custom_error_data(StrategyWorker, "AccessControlUnauthorizedAccount", ["address"], [dev_wallet2.address])
        + ENCODER_SEPARATOR
    ):
        controller.grantRole(CONTROLLER_CALLER_BYTES_ROLE, NULL_ADDRESS, {"from": dev_wallet2})
    assert controller.hasRole(CONTROLLER_CALLER_BYTES_ROLE, NULL_ADDRESS) == False


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
