from math import floor
from eth_abi import abi 
from helpers import encode_custom_error
from helpers import (
    get_strategy_vault,
    get_account_from_pk,
    check_network_is_mainnet_fork,
)
from brownie import (
    config,
    reverts,
    StrategyManager,
    PriceFeedsDataConsumer,
)


dev_wallet = get_account_from_pk(1)
dev_wallet2 = get_account_from_pk(2)

PERCENTAGE_FACTOR = 10_000
DEV_WALLET_LOW_DEPOSIT_TOKEN_AMOUNT = 100
DEV_WALLET_DEPOSIT_TOKEN_AMOUNT = 30_000
DEV_WALLET_WITHDRAW_TOKEN_AMOUNT = 29_900


################################ Contract Actions ################################


def test_whitelist_new_address_by_owner(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    deposit_asset_to_whitelist = configs["whitelisted_deposit_assets"][4]
    # Act
    strategy_manager.addWhitelistedDepositAssets([deposit_asset_to_whitelist], {"from": dev_wallet})
    # Assert
    assert strategy_manager.getWhitelistedDepositAssetAddresses() == [
        configs["whitelisted_deposit_assets"][0][0],
        configs["token_not_paired_with_weth_address"],
        configs["whitelisted_deposit_assets"][4][0],
    ]


def test_repeated_address_by_owner(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    deposit_asset_to_whitelist = configs["whitelisted_deposit_assets"][4]
    # Act
    strategy_manager.addWhitelistedDepositAssets([deposit_asset_to_whitelist], {"from": dev_wallet})
    # Assert
    assert (
        len(strategy_manager.getWhitelistedDepositAssetAddresses()) == 3
    )  # repeated address shoudn't be added to the list
    assert (
        strategy_manager.getWhitelistedDepositAsset(configs["whitelisted_deposit_assets"][4][0])
        == deposit_asset_to_whitelist
    )


def test_deactivate_whitelisted_address_by_owner(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    # Act
    whitelisted_deposit_asset_address = configs["whitelisted_deposit_assets"][4][0]
    strategy_manager.deactivateWhitelistedDepositAsset(whitelisted_deposit_asset_address, {"from": dev_wallet})
    assert strategy_manager.getWhitelistedDepositAsset(whitelisted_deposit_asset_address)[3] == False


def test_strategy_manager_default_parameters():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    max_number_of_actions_per_frequency = config["protocol-params"]["max_number_of_actions_per_frequency"]
    gas_cost_safety_factors = config["protocol-params"]["gas_cost_safety_factors"]
    deposit_token_price_safety_factor = config["protocol-params"]["deposit_token_price_safety_factor"]
    # Assert
    assert strategy_manager.getMaxExpectedGasUnits() == config["protocol-params"]["worker_max_expected_gas_units_wei"]
    assert strategy_manager.getMaxNumberOfActionsPerFrequency(0) == max_number_of_actions_per_frequency[0]
    assert strategy_manager.getMaxNumberOfActionsPerFrequency(1) == max_number_of_actions_per_frequency[1]
    assert strategy_manager.getMaxNumberOfActionsPerFrequency(2) == max_number_of_actions_per_frequency[2]
    assert strategy_manager.getMaxNumberOfActionsPerFrequency(3) == max_number_of_actions_per_frequency[3]
    assert strategy_manager.getGasCostSafetyFactor(20, 0) == gas_cost_safety_factors[0]  # 20 DAYS
    assert strategy_manager.getGasCostSafetyFactor(10, 1) == gas_cost_safety_factors[1]  # 10 WEEKS
    assert strategy_manager.getGasCostSafetyFactor(10, 2) == gas_cost_safety_factors[2]  # 20 WEEKS
    assert strategy_manager.getGasCostSafetyFactor(11, 3) == gas_cost_safety_factors[3]  # 11 MONTHS
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(0, 20, 0) == deposit_token_price_safety_factor[0][0]
    )  # 20 DAYS/STABLE
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(1, 20, 0) == deposit_token_price_safety_factor[1][0]
    )  # 20 DAYS/ETH_BTC
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(2, 20, 0) == deposit_token_price_safety_factor[2][0]
    )  # 20 DAYS/BLUE_CHIP
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(0, 10, 1) == deposit_token_price_safety_factor[0][1]
    )  # 10 WEEKS/STABLE
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(1, 10, 1) == deposit_token_price_safety_factor[1][1]
    )  # 10 WEEKS/ETH_BTC
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(2, 10, 1) == deposit_token_price_safety_factor[2][1]
    )  # 10 WEEKS/BLUE_CHIP
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(0, 10, 2) == deposit_token_price_safety_factor[0][2]
    )  # 20 WEEKS/STABLE
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(1, 10, 2) == deposit_token_price_safety_factor[1][2]
    )  # 20 WEEKS/ETH_BTC
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(2, 10, 2) == deposit_token_price_safety_factor[2][2]
    )  # 20 WEEKS/BLUE_CHIP

    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(0, 11, 3) == deposit_token_price_safety_factor[0][3]
    )  # 11 MONTHS/STABLE
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(1, 11, 3) == deposit_token_price_safety_factor[1][3]
    )  # 11 MONTHS/ETH_BTC
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(2, 11, 3) == deposit_token_price_safety_factor[2][3]
    )  # 11 MONTHS/BLUE_CHIP


def test_set_gas_cost_safety_factor_by_owner():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    new_gas_cost_safety_factor = 900
    # Act
    strategy_manager.setGasCostSafetyFactor(0, new_gas_cost_safety_factor, {"from": dev_wallet})  # <= 30 DAYS
    # Assert
    assert strategy_manager.getGasCostSafetyFactor(1, 1) == new_gas_cost_safety_factor  # 1 DAY


def test_set_deposit_token_price_safety_factor_by_owner():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    new_deposit_token_price_safety_factor = 100
    # Act
    strategy_manager.setDepositTokenPriceSafetyFactor(
        2, 3, new_deposit_token_price_safety_factor, {"from": dev_wallet}
    )  # > 180 DAYS/BLUE_CHIP
    # Assert
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(2, 7, 3) == new_deposit_token_price_safety_factor
    )  # 7 MONTH


def test_simulate_min_deposit_value(configs, deposit_token, gas_price):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    strategy_vault = get_strategy_vault(0)
    # Deposit in order to test simulateMinDepositValue with maxWithdraw(dev_wallet) > 0:
    strategy_vault.deposit(DEV_WALLET_LOW_DEPOSIT_TOKEN_AMOUNT, dev_wallet.address, {"from": dev_wallet})
    price_feeds_data_consumer = PriceFeedsDataConsumer[-1]
    (
        native_token_price,
        native_token_price_decimals,
    ) = price_feeds_data_consumer.getNativeTokenDataFeedLatestPriceAndDecimals()
    deposit_token_price, deposit_token_price_decimals = price_feeds_data_consumer.getDataFeedLatestPriceAndDecimals(
        configs["whitelisted_deposit_assets"][0][2]
    )

    depositor_previous_balance = strategy_vault.maxWithdraw(dev_wallet)
    max_number_of_strategy_actions = 12
    max_expected_gas_units = strategy_manager.getMaxExpectedGasUnits()
    gas_cost_safety_factor = strategy_manager.getGasCostSafetyFactor(
        max_number_of_strategy_actions, configs["buy_frequency"]
    )
    whitelisted_deposit_asset = configs["whitelisted_deposit_assets"][0]  # USDC.e
    deposit_token_price_safety_factor = strategy_manager.getDepositTokenPriceSafetyFactor(
        whitelisted_deposit_asset[1], max_number_of_strategy_actions, configs["buy_frequency"]
    )
    current_network_gas_price = gas_price
    deposit_token_decimals = deposit_token.decimals()
    expected_min_deposit_value = floor(
        int(
            int(
                native_token_price
                * PERCENTAGE_FACTOR
                * max_expected_gas_units
                * max_number_of_strategy_actions
                * current_network_gas_price
                * gas_cost_safety_factor
                * (10 ** (deposit_token_price_decimals + deposit_token_decimals))
            )
            / int(
                deposit_token_price
                * configs["treasury_percentage_fee_on_balance_update"]
                * deposit_token_price_safety_factor
                * (10 ** (18 + native_token_price_decimals))
            )
        )
    )
    expected_min_deposit_value = (
        expected_min_deposit_value - depositor_previous_balance
        if expected_min_deposit_value > depositor_previous_balance
        else 0
    )
    # Assert
    assert (
        strategy_manager.simulateMinDepositValue(
            whitelisted_deposit_asset,
            max_number_of_strategy_actions,
            configs["buy_frequency"],
            configs["treasury_percentage_fee_on_balance_update"],
            deposit_token_decimals,
            depositor_previous_balance,
            current_network_gas_price,
        )
        == expected_min_deposit_value
    )


def test_simulate_min_deposit_value_after_wallet_deposit(configs, deposit_token, gas_price):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    strategy_vault = get_strategy_vault(0)
    depositor_previous_balance = strategy_vault.balanceOf(dev_wallet)
    max_number_of_strategy_actions = 12
    whitelisted_deposit_asset = configs["whitelisted_deposit_assets"][0]  # USDC.e
    deposit_token_decimals = deposit_token.decimals()
    current_network_gas_price = gas_price
    min_deposit_balance_before = strategy_manager.simulateMinDepositValue(
        whitelisted_deposit_asset,
        max_number_of_strategy_actions,
        configs["buy_frequency"],
        configs["treasury_percentage_fee_on_balance_update"],
        deposit_token_decimals,
        depositor_previous_balance,
        current_network_gas_price,
    )
    # Act
    strategy_vault.deposit(DEV_WALLET_DEPOSIT_TOKEN_AMOUNT, dev_wallet.address, {"from": dev_wallet})
    new_depositor_previous_balance = strategy_vault.balanceOf(dev_wallet)
    min_deposit_balance_after = strategy_manager.simulateMinDepositValue(
        whitelisted_deposit_asset,
        max_number_of_strategy_actions,
        configs["buy_frequency"],
        configs["treasury_percentage_fee_on_balance_update"],
        deposit_token_decimals,
        new_depositor_previous_balance,
        current_network_gas_price,
    )
    expected_min_deposit_balance_after = (
        min_deposit_balance_before - DEV_WALLET_DEPOSIT_TOKEN_AMOUNT
        if min_deposit_balance_before > new_depositor_previous_balance
        else 0
    )
    # Assert
    assert min_deposit_balance_after == expected_min_deposit_balance_after


################################ Contract Validations ################################


def test_whitelist_addresses_by_non_owner(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    deposit_asset_to_whitelist = configs["whitelisted_deposit_assets"][1]
    # Act/ Assert
    with reverts(encode_custom_error(StrategyManager, "OwnableUnauthorizedAccount", []) + abi.encode(["address"], [dev_wallet2.address]).hex()):
        strategy_manager.addWhitelistedDepositAssets([deposit_asset_to_whitelist], {"from": dev_wallet2})


def test_deactivate_whitelisted_address_by_non_owner(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    deposit_asset_to_deactivate = configs["whitelisted_deposit_assets"][4][0]
    # Act / Assert
    with reverts(encode_custom_error(StrategyManager, "OwnableUnauthorizedAccount", []) + abi.encode(["address"], [dev_wallet2.address]).hex()):
        strategy_manager.deactivateWhitelistedDepositAsset(deposit_asset_to_deactivate, {"from": dev_wallet2})


def test_change_max_expected_gas_units_by_non_owner(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    # Act / Assert
    with reverts(encode_custom_error(StrategyManager, "OwnableUnauthorizedAccount", []) + abi.encode(["address"], [dev_wallet2.address]).hex()):
        strategy_manager.setMaxExpectedGasUnits(1, {"from": dev_wallet2})


def test_set_gas_cost_safety_factor_by_non_owner():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    new_gas_cost_safety_factor = 800
    # Act / Assert
    with reverts(encode_custom_error(StrategyManager, "OwnableUnauthorizedAccount", []) + abi.encode(["address"], [dev_wallet2.address]).hex()):
        strategy_manager.setGasCostSafetyFactor(0, new_gas_cost_safety_factor, {"from": dev_wallet2})  # <= 30 DAYS


def test_set_deposit_token_price_safety_factor_by_non_owner():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    new_deposit_token_price_safety_factor = 200
    # Act/Assert
    with reverts(encode_custom_error(StrategyManager, "OwnableUnauthorizedAccount", []) + abi.encode(["address"], [dev_wallet2.address]).hex()):
        strategy_manager.setDepositTokenPriceSafetyFactor(
            2, 3, new_deposit_token_price_safety_factor, {"from": dev_wallet2}
        )  # > 180 DAYS/BLUE_CHIP


def test_deposit_generating_to_many_actions(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    strategy_vault = get_strategy_vault(0)
    max_number_of_actions_per_frequency = strategy_manager.getMaxNumberOfActionsPerFrequency(configs["buy_frequency"])
    depositor_total_periodic_buy_amount = strategy_vault.getDepositorTotalPeriodicBuyAmount(dev_wallet)
    max_wallet_deposit_balance = max_number_of_actions_per_frequency * depositor_total_periodic_buy_amount
    # Act/Assert - Deposit must fail because dev_wallet already had balance in this strategy
    with reverts(encode_custom_error(StrategyManager, "InvalidParameters", []) + abi.encode(["string"], ["Max number of actions exceeds the limit"]).hex()):
        strategy_vault.deposit(max_wallet_deposit_balance, dev_wallet.address, {"from": dev_wallet})
