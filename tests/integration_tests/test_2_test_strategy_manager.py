import pytest
from helpers import (
    get_account_from_pk,
    check_network_is_mainnet_fork,
)
from brownie import (
    StrategyManager,
    config,
    exceptions,
)

dev_wallet = get_account_from_pk(1)
dev_wallet2 = get_account_from_pk(2)


################################ Contract Actions ################################


def test_whitelist_new_address_by_owner(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    deposit_asset_to_whitelist = (configs["dex_main_token_address"], 1, configs["native_token_data_feed_address"], True)
    # Act
    strategy_manager.addWhitelistedDepositAssets([deposit_asset_to_whitelist], {"from": dev_wallet})
    # Assert
    assert strategy_manager.getWhitelistedDepositAssetAddresses() == [
        configs["deposit_token_address"],
        configs["dex_main_token_address"],
    ]


def test_repeated_address_by_owner(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    deposit_asset_to_whitelist = (configs["dex_main_token_address"], 2, configs["native_token_data_feed_address"], True)
    # Act
    strategy_manager.addWhitelistedDepositAssets([deposit_asset_to_whitelist], {"from": dev_wallet})
    # Assert
    assert (
        len(strategy_manager.getWhitelistedDepositAssetAddresses()) == 2
    )  # repeated address shoudn't be added to the list
    assert strategy_manager.getWhitelistedDepositAsset(configs["dex_main_token_address"]) == deposit_asset_to_whitelist


def test_deactivate_whitelisted_address_by_owner(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    # Act
    strategy_manager.deactivateWhitelistedDepositAsset(configs["dex_main_token_address"], {"from": dev_wallet})
    assert strategy_manager.getWhitelistedDepositAsset(configs["dex_main_token_address"]) == (
        configs["dex_main_token_address"],
        2,
        configs["native_token_data_feed_address"],
        False,
    )


def test_strategy_manager_default_parameters():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    max_number_of_actions_per_frequency = config["protocol-params"]["max_number_of_actions_per_frequency"]
    gas_cost_safety_factors = config["protocol-params"]["gas_cost_safety_factors"]
    deposit_token_price_safety_factor = config["protocol-params"]["deposit_token_price_safety_factor"]
    # Assert
    assert strategy_manager.getMaxExpectedGasUnits() == config["protocol-params"]["worker_max_expected_gas_units_wei"]
    assert (
        strategy_manager.getMaxNumberOfActionsPerFrequency(0) == max_number_of_actions_per_frequency[0]
    )  # TODO: Remove after prod
    assert strategy_manager.getMaxNumberOfActionsPerFrequency(1) == max_number_of_actions_per_frequency[1]
    assert strategy_manager.getMaxNumberOfActionsPerFrequency(2) == max_number_of_actions_per_frequency[2]
    assert strategy_manager.getMaxNumberOfActionsPerFrequency(3) == max_number_of_actions_per_frequency[3]
    assert strategy_manager.getMaxNumberOfActionsPerFrequency(4) == max_number_of_actions_per_frequency[4]
    assert strategy_manager.getGasCostSafetyFactor(20, 1) == gas_cost_safety_factors[0]  # 20 DAYS
    assert strategy_manager.getGasCostSafetyFactor(10, 2) == gas_cost_safety_factors[1]  # 10 WEEKS
    assert strategy_manager.getGasCostSafetyFactor(10, 3) == gas_cost_safety_factors[2]  # 20 WEEKS
    assert strategy_manager.getGasCostSafetyFactor(11, 4) == gas_cost_safety_factors[3]  # 11 MONTHS
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(0, 20, 1) == deposit_token_price_safety_factor[0][0]
    )  # 20 DAYS/STABLE
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(1, 20, 1) == deposit_token_price_safety_factor[1][0]
    )  # 20 DAYS/ETH_BTC
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(2, 20, 1) == deposit_token_price_safety_factor[2][0]
    )  # 20 DAYS/BLUE_CHIP
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(0, 10, 2) == deposit_token_price_safety_factor[0][1]
    )  # 10 WEEKS/STABLE
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(1, 10, 2) == deposit_token_price_safety_factor[1][1]
    )  # 10 WEEKS/ETH_BTC
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(2, 10, 2) == deposit_token_price_safety_factor[2][1]
    )  # 10 WEEKS/BLUE_CHIP
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(0, 10, 3) == deposit_token_price_safety_factor[0][2]
    )  # 20 WEEKS/STABLE
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(1, 10, 3) == deposit_token_price_safety_factor[1][2]
    )  # 20 WEEKS/ETH_BTC
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(2, 10, 3) == deposit_token_price_safety_factor[2][2]
    )  # 20 WEEKS/BLUE_CHIP

    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(0, 11, 4) == deposit_token_price_safety_factor[0][3]
    )  # 11 MONTHS/STABLE
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(1, 11, 4) == deposit_token_price_safety_factor[1][3]
    )  # 11 MONTHS/ETH_BTC
    assert (
        strategy_manager.getDepositTokenPriceSafetyFactor(2, 11, 4) == deposit_token_price_safety_factor[2][3]
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
        strategy_manager.getDepositTokenPriceSafetyFactor(2, 7, 4) == new_deposit_token_price_safety_factor
    )  # 7 MONTH


################################ Contract Validations ################################


def test_whitelist_addresses_by_non_owner(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    deposit_asset_to_whitelist = (configs["dex_main_token_address"], 1, configs["native_token_data_feed_address"], True)
    # Act/ Assert
    with pytest.raises(exceptions.VirtualMachineError):
        strategy_manager.addWhitelistedDepositAssets([deposit_asset_to_whitelist], {"from": dev_wallet2})


def test_deactivate_whitelisted_address_by_non_owner(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        strategy_manager.deactivateWhitelistedDepositAsset(configs["deposit_token_address"], {"from": dev_wallet2})


def test_change_max_expected_gas_units_by_non_owner(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        strategy_manager.setMaxExpectedGasUnits(1, {"from": dev_wallet2})


def test_set_gas_cost_safety_factor_by_non_owner():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    new_gas_cost_safety_factor = 800
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        strategy_manager.setGasCostSafetyFactor(0, new_gas_cost_safety_factor, {"from": dev_wallet2})  # <= 30 DAYS


def test_set_deposit_token_price_safety_factor_by_non_owner():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_manager = StrategyManager[-1]
    new_deposit_token_price_safety_factor = 200
    # Act/Assert
    with pytest.raises(exceptions.VirtualMachineError):
        strategy_manager.setDepositTokenPriceSafetyFactor(
            2, 3, new_deposit_token_price_safety_factor, {"from": dev_wallet2}
        )  # > 180 DAYS/BLUE_CHIP
