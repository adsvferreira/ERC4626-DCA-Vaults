import pytest
from typing import Tuple

# from eth_utils.abi import function_abi_to_4byte_selector, collapse_if_tuple
from helpers import (
    RoundingMethod,
    get_strategy_vault,
    get_account_from_pk,
    convert_shares_to_assets,
    convert_assets_to_shares,
    perc_mul_contracts_simulate,
    check_network_is_mainnet_fork,
    NULL_ADDRESS,
)
from scripts.deploy import (
    deploy_controller,
    deploy_treasury_vault,
    deploy_strategy_worker,
    deploy_strategy_manager,
    deploy_automated_vaults_factory,
    deploy_price_feeds_data_consumer,
)
from brownie import (
    TreasuryVault,
    StrategyWorker,
    StrategyManager,
    AutomatedVaultERC4626,
    AutomatedVaultsFactory,
    Wei,
    config,
    network,
    exceptions,
)

# In order to run this tests a .env file must be created in the project's root containing 2 dev wallet private keys.
# Ex:
# export PRIVATE_KEY_1=...
# export PRIVATE_KEY_2=...
# export PRIVATE_KEY_3...
#
# COMMAND TO EXECUTE ON ARBITRUM LOCAL FORK: brownie test -s --network arbitrum-main-fork

dev_wallet = get_account_from_pk(1)
dev_wallet2 = get_account_from_pk(2)
empty_wallet = get_account_from_pk(3)

DEV_WALLET_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT = 999_999_999_999_999_999_999_999_999_999
DEV_WALLET_DEPOSIT_TOKEN_AMOUNT = 20_000
DEV_WALLET_2ND_DEPOSIT_TOKEN_AMOUNT = 10_000
DEV_WALLET2_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT = 999_999_999_999_999_999_999_999_999_999
DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT = 20_000
DEV_WALLET_WITHDRAW_TOKEN_AMOUNT = 10_000
DEPOSIT_TOKEN_AMOUNT_TRANSFER_TO_VAULT = 20_000
GT_BALANCE_TESTING_VALUE = 999_999_999_999_999_999_999_999_999_999
NEGATIVE_AMOUNT_TESTING_VALUE = -1


################################ Contract Actions ################################


def test_create_new_vault(configs, deposit_token, gas_price):
    check_network_is_mainnet_fork()
    # Arrange
    verify_flag = config["networks"][network.show_active()]["verify"]
    wallet_initial_native_balance = dev_wallet.balance()
    # Act

    # Protocolo initial contracts deployment + setup
    treasury_vault = deploy_treasury_vault(dev_wallet, verify_flag)
    treasury_address = treasury_vault.address
    controller = deploy_controller(dev_wallet, verify_flag)
    controller_address = controller.address
    strategy_worker = deploy_strategy_worker(
        dev_wallet,
        verify_flag,
        configs["dex_router_address"],
        configs["dex_main_token_address"],
        controller_address,
    )
    price_feeds_data_consumer = deploy_price_feeds_data_consumer(
        dev_wallet, verify_flag, configs["native_token_data_feed_address"]
    )
    price_feeds_data_consumer_address = price_feeds_data_consumer.address
    strategy_manager = deploy_strategy_manager(dev_wallet, verify_flag, price_feeds_data_consumer_address)
    strategy_manager_address = strategy_manager.address
    # setMaxExpectedGasUnits must be changed to a unrealistically low value in order to avoid erros when testing for low balances.
    # Such a low minimum allowed deposit makes the vaults prone to Inflation attacks if
    # (see https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/extensions/ERC4626.sol)
    # Make sure to set maxExpectedGasUnits with a real value in prod!!
    StrategyManager[-1].setMaxExpectedGasUnits(
        config["protocol-params"]["worker_max_expected_gas_units_wei"], {"from": dev_wallet}
    )
    vaults_factory = deploy_automated_vaults_factory(
        dev_wallet,
        verify_flag,
        configs["dex_factory_address"],
        configs["dex_main_token_address"],
        treasury_address,
        strategy_manager_address,
        configs["treasury_fixed_fee_on_vault_creation"],
        configs["creator_percentage_fee_on_deposit"],
        configs["treasury_percentage_fee_on_balance_update"],
    )
    whitelisted_deposit_asset = configs["whitelisted_deposit_assets"][0]
    strategy_manager.addWhitelistedDepositAssets([whitelisted_deposit_asset], {"from": dev_wallet})
    treasury_vault_initial_native_balance = treasury_vault.balance()
    treasury_vault_initial_erc20_balance = deposit_token.balanceOf(treasury_address)
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    deposit_token.approve(
        vaults_factory.address,
        DEV_WALLET_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT,
        {"from": dev_wallet},
    )
    tx = vaults_factory.createVault(
        init_vault_from_factory_params,
        strategy_params,
        DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
        {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"], "gas_price": gas_price},
    )
    strategy_vault = get_strategy_vault()
    strategy_vault.approve(strategy_worker.address, DEV_WALLET_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT, {"from": dev_wallet})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    total_shares = strategy_vault.totalSupply()
    total_assets = strategy_vault.totalAssets()
    expected_final_wallet_lp_balance = convert_assets_to_shares(
        DEV_WALLET_DEPOSIT_TOKEN_AMOUNT, total_shares, total_assets
    )
    final_wallet_assets = strategy_vault.maxWithdraw(dev_wallet)
    wallet_final_native_balance = dev_wallet.balance()
    treasury_vault_final_native_balance = treasury_vault.balance()
    treasury_vault_final_erc20_balance = deposit_token.balanceOf(treasury_address)
    native_token_fee_paid = (
        wallet_initial_native_balance - wallet_final_native_balance - (tx.gas_price * tx.gas_used)
    )  # gas price is 0 in local forked testnet
    final_vault_depositors_list_length = strategy_vault.allDepositorsLength()
    final_wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet)
    expected_final_wallet_buy_amounts = [
        perc_mul_contracts_simulate(DEV_WALLET_DEPOSIT_TOKEN_AMOUNT, buy_perc)
        for buy_perc in configs["buy_percentages"]
    ]
    vault_is_active = strategy_vault.getInitMultiAssetVaultParams()[5]
    final_depositor_total_periodic_buy_amount = strategy_vault.getDepositorTotalPeriodicBuyAmount(dev_wallet)
    # Assert
    assert vaults_factory.allVaultsLength() == 1
    assert vaults_factory.getAllVaultsPerStrategyWorker(strategy_params[2]) == [get_strategy_vault().address]
    assert bool(vaults_factory.getUserVaults(dev_wallet))
    assert treasury_vault_initial_native_balance == 0
    assert treasury_vault_initial_erc20_balance == 0
    assert treasury_vault_final_native_balance == configs["treasury_fixed_fee_on_vault_creation"]
    assert treasury_vault_final_erc20_balance == 0  # Only native token fee on creation
    assert native_token_fee_paid == configs["treasury_fixed_fee_on_vault_creation"]
    assert strategy_vault.feesAccruedByCreator() == 0  # The creator doesn't get fees from it's own deposit.
    assert final_wallet_lp_balance == expected_final_wallet_lp_balance
    assert final_wallet_assets == DEV_WALLET_DEPOSIT_TOKEN_AMOUNT
    assert final_vault_depositors_list_length == 1
    assert final_wallet_buy_amounts == expected_final_wallet_buy_amounts
    assert vault_is_active == True
    assert final_depositor_total_periodic_buy_amount == sum(expected_final_wallet_buy_amounts)
    assert strategy_vault.getBatchDepositorAddresses(99, 0) == [dev_wallet.address]


def test_created_vault_init_params(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    (
        name,
        symbol,
        treasury_address,
        creator_address,
        factory_address,
        is_active,
        deposit_asset,
        buy_assets,
        creator_perc_fee,
        treasury_perc_fee,
    ) = strategy_vault.getInitMultiAssetVaultParams()
    # Act
    # Assert
    assert strategy_vault.feesAccruedByCreator() == 0
    assert name == configs["vault_name"]
    assert symbol == configs["vault_symbol"]
    assert treasury_address == TreasuryVault[-1].address
    assert dev_wallet == creator_address
    assert factory_address == AutomatedVaultsFactory[-1].address
    assert is_active == True
    assert deposit_asset == configs["deposit_token_address"]
    assert buy_assets == configs["buy_token_addresses"]
    assert creator_perc_fee == configs["creator_percentage_fee_on_deposit"]
    assert treasury_perc_fee == configs["treasury_percentage_fee_on_balance_update"]


def test_created_vault_strategy_params(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    (
        buy_percentages,
        buy_frequency,
        strategy_worker_address,
        strategy_manager_address,
    ) = strategy_vault.getStrategyParams()
    # Act
    # Assert
    assert buy_percentages == configs["buy_percentages"]
    assert buy_frequency == configs["buy_frequency"]
    assert strategy_worker_address == StrategyWorker[-1].address
    assert strategy_manager_address == StrategyManager[-1].address


def test_created_vault_buy_tokens(configs):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    buy_token_addresses = strategy_vault.getBuyAssetAddresses()
    # Act
    # Assert
    assert strategy_vault.buyAssetsLength() == len(configs["buy_token_addresses"])
    assert buy_token_addresses == configs["buy_token_addresses"]
    assert strategy_vault.asset() == configs["deposit_token_address"]


def test_transfer_deposit_token_to_vault(deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    initial_total_shares = strategy_vault.totalSupply()
    initial_total_assets = strategy_vault.totalAssets()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    expected_wallet_lp_balance = convert_assets_to_shares(
        DEV_WALLET_DEPOSIT_TOKEN_AMOUNT, initial_total_shares, initial_total_assets
    )
    initial_wallet_assets = strategy_vault.maxWithdraw(dev_wallet)

    # Act
    # Execute deposit token transfer directly to strategy vault -> assets to shares ratio != 1:1
    deposit_token.transfer(strategy_vault.address, DEPOSIT_TOKEN_AMOUNT_TRANSFER_TO_VAULT, {"from": dev_wallet})

    final_total_shares = strategy_vault.totalSupply()
    final_total_assets = strategy_vault.totalAssets()
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_wallet_assets = strategy_vault.maxWithdraw(dev_wallet)
    expected_final_wallet_assets = convert_shares_to_assets(
        final_wallet_lp_balance, final_total_shares, final_total_assets
    )

    # Assert
    assert initial_wallet_lp_balance == expected_wallet_lp_balance
    assert initial_wallet_assets == DEV_WALLET_DEPOSIT_TOKEN_AMOUNT
    assert initial_wallet_lp_balance == final_wallet_lp_balance
    assert final_wallet_assets == expected_final_wallet_assets


def test_deposit_owned_vault(deposit_token, gas_price):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    initial_total_shares = strategy_vault.totalSupply()
    initial_total_assets = strategy_vault.totalAssets()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_wallet_assets = strategy_vault.maxWithdraw(dev_wallet)
    initial_initial_wallet_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet)
    initial_wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet)
    initial_depositor_total_periodic_buy_amount = strategy_vault.getDepositorTotalPeriodicBuyAmount(dev_wallet)
    # Act
    deposit_token.approve(
        strategy_vault.address,
        DEV_WALLET_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT,
        {"from": dev_wallet},
    )
    strategy_vault.deposit(
        DEV_WALLET_2ND_DEPOSIT_TOKEN_AMOUNT, dev_wallet.address, {"from": dev_wallet, "gas_price": gas_price}
    )
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    expected_final_wallet_lp_balance = initial_wallet_lp_balance + convert_assets_to_shares(
        DEV_WALLET_2ND_DEPOSIT_TOKEN_AMOUNT, initial_total_shares, initial_total_assets
    )
    final_wallet_assets = strategy_vault.maxWithdraw(dev_wallet)
    expected_final_wallet_assets = initial_wallet_assets + DEV_WALLET_2ND_DEPOSIT_TOKEN_AMOUNT
    final_vault_lp_supply = strategy_vault.totalSupply()
    expected_final_vault_lp_supply = initial_total_shares + convert_assets_to_shares(
        DEV_WALLET_2ND_DEPOSIT_TOKEN_AMOUNT, initial_total_shares, initial_total_assets
    )
    final_vault_depositors_list_length = strategy_vault.allDepositorsLength()
    depositor_addresses = strategy_vault.getBatchDepositorAddresses(99, 0)
    final_vault_is_active = strategy_vault.getInitMultiAssetVaultParams()[5]
    final_initial_wallet_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet)
    final_wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet)
    final_depositor_total_periodic_buy_amount = strategy_vault.getDepositorTotalPeriodicBuyAmount(dev_wallet)
    # Assert
    assert depositor_addresses == [dev_wallet.address]
    assert final_wallet_lp_balance == expected_final_wallet_lp_balance
    assert final_wallet_assets == expected_final_wallet_assets
    assert final_vault_lp_supply == expected_final_vault_lp_supply
    assert final_vault_depositors_list_length == 1  # Depositor is the creator
    assert final_vault_is_active == True
    assert (
        final_initial_wallet_deposit_balance == initial_initial_wallet_deposit_balance
    )  # Can only be reset when depositor balance == 0
    assert final_wallet_buy_amounts == initial_wallet_buy_amounts
    assert final_depositor_total_periodic_buy_amount == initial_depositor_total_periodic_buy_amount


def test_lp_token_transfer_to_future_depositor_before_deposit_not_owned_vault(configs, deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    initial_wallet2_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    initial_wallet2_asset_balance = strategy_vault.maxWithdraw(dev_wallet2)
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_wallet_asset_balance = strategy_vault.maxWithdraw(dev_wallet)
    initial_initial_wallet2_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet2)
    initial_wallet2_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet2)
    initial_wallet2_total_periodic_buy_amount = strategy_vault.getDepositorTotalPeriodicBuyAmount(dev_wallet2)
    initial_total_supply = strategy_vault.totalSupply()
    initial_total_assets = strategy_vault.totalAssets()
    shares_transfer_amount = 1
    # Act
    strategy_vault.transfer(dev_wallet2.address, shares_transfer_amount, {"from": dev_wallet})
    final_wallet2_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    final_wallet2_asset_balance = strategy_vault.maxWithdraw(dev_wallet2)
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_wallet_asset_balance = strategy_vault.maxWithdraw(dev_wallet)
    final_initial_wallet2_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet2)
    final_wallet2_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet2)
    final_wallet2_total_periodic_buy_amount = strategy_vault.getDepositorTotalPeriodicBuyAmount(dev_wallet2)
    final_total_supply = strategy_vault.totalSupply()
    final_total_assets = strategy_vault.totalAssets()
    # Assert
    assert final_wallet2_lp_balance == initial_wallet2_lp_balance + shares_transfer_amount
    assert final_wallet2_asset_balance == initial_wallet2_asset_balance + convert_shares_to_assets(
        shares_transfer_amount, initial_total_supply, initial_total_assets
    )
    assert final_wallet_lp_balance == initial_wallet_lp_balance - shares_transfer_amount
    assert final_wallet_asset_balance == initial_wallet_asset_balance - convert_shares_to_assets(
        shares_transfer_amount, initial_total_supply, initial_total_assets
    )
    assert final_total_supply == initial_total_supply
    assert final_total_assets == initial_total_assets
    # The following vault properties should only be updated when interacting with `deposit` function
    assert final_initial_wallet2_deposit_balance == initial_initial_wallet2_deposit_balance
    assert final_wallet2_buy_amounts == initial_wallet2_buy_amounts
    assert final_wallet2_total_periodic_buy_amount == initial_wallet2_total_periodic_buy_amount


def test_deposit_not_owned_vault(configs, deposit_token, gas_price):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_wallet2_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    initial_vault_lp_supply = strategy_vault.totalSupply()
    initial_total_assets = strategy_vault.totalAssets()
    initial_initial_wallet_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet)
    initial_wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet)
    initial_fees_accrued_by_creator = strategy_vault.feesAccruedByCreator()
    creator_fee_on_deposit = perc_mul_contracts_simulate(
        DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT, configs["creator_percentage_fee_on_deposit"]
    )
    expected_final_wallet2_buy_amounts = [
        perc_mul_contracts_simulate(DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT - creator_fee_on_deposit, buy_perc)
        for buy_perc in configs["buy_percentages"]
    ]
    # Act
    deposit_token.approve(
        strategy_vault.address,
        DEV_WALLET2_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT,
        {"from": dev_wallet2},
    )
    strategy_vault.deposit(
        DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT, dev_wallet2.address, {"from": dev_wallet2, "gas_price": gas_price}
    )
    strategy_vault.approve(
        StrategyWorker[-1].address, DEV_WALLET2_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT, {"from": dev_wallet2}
    )
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    expected_final_wallet_lp_balance = initial_wallet_lp_balance + convert_assets_to_shares(
        creator_fee_on_deposit, initial_vault_lp_supply, initial_total_assets
    )
    final_wallet_assets = strategy_vault.maxWithdraw(dev_wallet)
    final_wallet2_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    expected_final_wallet2_lp_balance = initial_wallet2_lp_balance + convert_assets_to_shares(
        DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT - creator_fee_on_deposit, initial_vault_lp_supply, initial_total_assets
    )
    final_wallet2_assets = strategy_vault.maxWithdraw(dev_wallet2)
    final_vault_lp_supply = strategy_vault.totalSupply()
    final_total_assets = strategy_vault.totalAssets()
    expected_final_wallet_assets = convert_shares_to_assets(
        expected_final_wallet_lp_balance, final_vault_lp_supply, final_total_assets
    )
    expected_final_wallet2_assets = convert_shares_to_assets(
        expected_final_wallet2_lp_balance, final_vault_lp_supply, final_total_assets
    )
    expected_final_total_assets = initial_total_assets + DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT
    expected_final_vault_lp_supply = initial_vault_lp_supply + convert_assets_to_shares(
        DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT, initial_vault_lp_supply, initial_total_assets
    )
    final_vault_depositors_list_length = strategy_vault.allDepositorsLength()
    second_depositor_address = strategy_vault.getBatchDepositorAddresses(1, 1)[0]
    final_initial_wallet_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet)
    final_wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet)
    final_initial_wallet2_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet2)
    final_wallet2_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet2)
    final_depositor_total_periodic_buy_amount = strategy_vault.getDepositorTotalPeriodicBuyAmount(dev_wallet2)
    # Assert
    assert strategy_vault.feesAccruedByCreator() == initial_fees_accrued_by_creator + creator_fee_on_deposit
    assert final_vault_lp_supply == expected_final_vault_lp_supply
    assert final_total_assets == expected_final_total_assets
    assert final_vault_depositors_list_length == 2
    assert second_depositor_address == dev_wallet2.address
    assert final_wallet2_lp_balance == expected_final_wallet2_lp_balance
    assert final_wallet2_assets == expected_final_wallet2_assets
    assert final_wallet_lp_balance == expected_final_wallet_lp_balance
    assert final_wallet_assets == expected_final_wallet_assets
    assert initial_initial_wallet_deposit_balance == final_initial_wallet_deposit_balance
    assert initial_wallet_buy_amounts == final_wallet_buy_amounts
    assert final_initial_wallet2_deposit_balance == DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT - creator_fee_on_deposit
    assert final_wallet2_buy_amounts == expected_final_wallet2_buy_amounts
    assert final_depositor_total_periodic_buy_amount == sum(expected_final_wallet2_buy_amounts)


def test_partial_withdraw():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_vault_lp_supply = strategy_vault.totalSupply()
    initial_total_assets = strategy_vault.totalAssets()
    # Act
    strategy_vault.withdraw(DEV_WALLET_WITHDRAW_TOKEN_AMOUNT, dev_wallet, dev_wallet, {"from": dev_wallet})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_wallet_assets = strategy_vault.maxWithdraw(dev_wallet)
    expected_final_wallet_lp_balance = initial_wallet_lp_balance - convert_assets_to_shares(
        DEV_WALLET_WITHDRAW_TOKEN_AMOUNT, initial_vault_lp_supply, initial_total_assets, RoundingMethod.CEIL
    )
    final_vault_lp_supply = strategy_vault.totalSupply()
    final_total_assets = strategy_vault.totalAssets()
    expected_final_wallet_assets = convert_shares_to_assets(
        expected_final_wallet_lp_balance, final_vault_lp_supply, final_total_assets
    )
    expected_final_vault_lp_supply = initial_vault_lp_supply - convert_assets_to_shares(
        DEV_WALLET_WITHDRAW_TOKEN_AMOUNT, initial_vault_lp_supply, initial_total_assets, RoundingMethod.CEIL
    )
    expected_final_total_assets = convert_shares_to_assets(
        expected_final_vault_lp_supply, initial_vault_lp_supply, initial_total_assets, RoundingMethod.CEIL
    )
    # Assert
    assert final_vault_lp_supply == expected_final_vault_lp_supply
    assert final_total_assets == expected_final_total_assets
    assert final_wallet_lp_balance == expected_final_wallet_lp_balance
    assert final_wallet_assets == expected_final_wallet_assets


def test_max_withdraw():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    max_deposit_wallet_assets = strategy_vault.maxWithdraw(dev_wallet)
    initial_vault_total_assets = strategy_vault.totalAssets()
    initial_vault_lp_supply = strategy_vault.totalSupply()
    # Act
    strategy_vault.withdraw(max_deposit_wallet_assets, dev_wallet, dev_wallet, {"from": dev_wallet})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_wallet_assets = strategy_vault.maxWithdraw(dev_wallet)
    final_vault_lp_supply = strategy_vault.totalSupply()
    final_vault_total_assets = strategy_vault.totalAssets()
    expected_final_vault_total_assets = initial_vault_total_assets - max_deposit_wallet_assets
    expected_final_wallet_lp_balance = initial_wallet_lp_balance - convert_assets_to_shares(
        max_deposit_wallet_assets, initial_vault_lp_supply, initial_vault_total_assets, RoundingMethod.CEIL
    )
    expected_vault_lp_supply = initial_vault_lp_supply - convert_assets_to_shares(
        max_deposit_wallet_assets, initial_vault_lp_supply, initial_vault_total_assets, RoundingMethod.CEIL
    )
    # Assert
    assert final_wallet_assets == 0
    assert (
        final_wallet_lp_balance == expected_final_wallet_lp_balance
    )  # Not zero due to `_convertToAssets` roundings. Dust shares balance correspond to less than 1 asset (assets/shares ratio = 1:10**(18))
    assert final_vault_total_assets == expected_final_vault_total_assets
    assert final_vault_lp_supply == expected_vault_lp_supply


def test_zero_value_withdraw(configs, deposit_token, gas_price):
    check_network_is_mainnet_fork()
    # Arrange
    # New vault creation is not required for this particular test. This was done in order to have multiple vaults created for further tests.
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    vaults_factory.createVault(
        init_vault_from_factory_params,
        strategy_params,
        DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
        {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"], "gas_price": gas_price},
    )
    strategy_vault2 = get_strategy_vault(1)
    strategy_vault2.approve(
        StrategyWorker[-1].address, DEV_WALLET2_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT, {"from": dev_wallet2}
    )
    deposit_token.approve(
        strategy_vault2.address,
        DEV_WALLET2_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT,
        {"from": dev_wallet2},
    )
    strategy_vault2.deposit(DEV_WALLET_2ND_DEPOSIT_TOKEN_AMOUNT, dev_wallet2.address, {"from": dev_wallet2})
    strategy_vault2.approve(
        StrategyWorker[-1].address, DEV_WALLET2_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT, {"from": dev_wallet2}
    )
    initial_wallet2_lp_balance = strategy_vault2.balanceOf(dev_wallet2)
    initial_vault_lp_supply = strategy_vault2.totalSupply()
    initial_vault_depositors_list_length = strategy_vault2.allDepositorsLength()
    initial_vault_is_active = strategy_vault2.getInitMultiAssetVaultParams()[5]
    initial_initial_wallet_deposit_balance = strategy_vault2.getInitialDepositBalance(dev_wallet)
    initial_wallet_buy_amounts = strategy_vault2.getDepositorBuyAmounts(dev_wallet)
    # Act
    strategy_vault2.withdraw(0, dev_wallet2, dev_wallet2, {"from": dev_wallet2})
    final_wallet2_lp_balance = strategy_vault2.balanceOf(dev_wallet2)
    final_vault_lp_supply = strategy_vault2.totalSupply()
    final_vault_depositors_list_length = strategy_vault2.allDepositorsLength()
    final_vault_is_active = strategy_vault2.getInitMultiAssetVaultParams()[5]
    final_initial_wallet_deposit_balance = strategy_vault2.getInitialDepositBalance(dev_wallet)
    final_wallet_buy_amounts = strategy_vault2.getDepositorBuyAmounts(dev_wallet)
    # Assert
    assert final_vault_lp_supply == initial_vault_lp_supply
    assert final_wallet2_lp_balance == initial_wallet2_lp_balance
    assert final_vault_depositors_list_length == initial_vault_depositors_list_length
    assert final_vault_is_active == initial_vault_is_active
    assert final_initial_wallet_deposit_balance == initial_initial_wallet_deposit_balance
    assert final_wallet_buy_amounts == initial_wallet_buy_amounts


def test_user_with_vaults_return_vaults(configs):
    vaults_factory = AutomatedVaultsFactory[-1]
    assert len(vaults_factory.getUserVaults(dev_wallet.address)) > 0


def test_user_without_vault_returns_no_vaults():
    vaults_factory = AutomatedVaultsFactory[-1]
    assert len(vaults_factory.getUserVaults(empty_wallet.address)) == 0


def test_get_all_depositor_addresses():
    check_network_is_mainnet_fork()
    # Vaults have been created in previous tests.
    vault = get_strategy_vault()
    depositors_len = vault.allDepositorsLength()
    assert len(vault.getBatchDepositorAddresses(depositors_len, 0)) == depositors_len


def test_get_all_depositor_addresses_with_offset():
    check_network_is_mainnet_fork()
    # Vaults have been created in previous tests.
    vault = get_strategy_vault()
    depositors_len = vault.allDepositorsLength()
    assert len(vault.getBatchDepositorAddresses(depositors_len - 2, 0)) == depositors_len - 2


def test_get_all_depositor_addresses_with_limit_bigger_than_length():
    check_network_is_mainnet_fork()
    # Vaults have been created in previous tests.
    vault = get_strategy_vault()
    depositors_len = vault.allDepositorsLength()
    depositors = vault.getBatchDepositorAddresses(depositors_len + 1, 1)
    assert len(depositors) == depositors_len - 1


def test_get_all_vaults(configs):
    check_network_is_mainnet_fork()
    vaults_factory = AutomatedVaultsFactory[-1]
    assert len(vaults_factory.getBatchVaults(vaults_factory.allVaultsLength(), 0)) == vaults_factory.allVaultsLength()


def test_get_all_vaults_with_offset():
    check_network_is_mainnet_fork()
    vaults_factory = AutomatedVaultsFactory[-1]
    # 2 vaults have been created at this point
    n_requested_vaults = 1
    assert len(vaults_factory.getBatchVaults(99, 1)) == n_requested_vaults


def test_get_all_vaults_with_limit_bigger_than_vault_length():
    vaults_factory = AutomatedVaultsFactory[-1]
    vaults_len = vaults_factory.allVaultsLength()
    # Act / Assert
    vaults = vaults_factory.getBatchVaults(vaults_len + 1, 1)
    assert len(vaults) == vaults_len - 1


################################ Contract Validations ################################


def test_instantiate_strategy_from_non_factory_address(configs):
    check_network_is_mainnet_fork()
    # Arrange
    verify_flag = config["networks"][network.show_active()]["verify"]
    strategy_params, _ = __get_default_strategy_and_init_vault_params(configs)
    init_vault_params = __get_init_vault_params(configs, dev_wallet)
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        AutomatedVaultERC4626.deploy(
            init_vault_params,
            strategy_params,
            {"from": dev_wallet},
            publish_source=verify_flag,
        )


def test_create_strategy_with_insufficient_ether_balance(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    # Act / Assert
    assert empty_wallet.balance() == 0
    with pytest.raises(ValueError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            {"from": empty_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )


def test_create_strategy_with_insufficient_ether_sent_as_fee(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"] - 1},
        )


def test_create_strategy_with_null_deposit_asset_address(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    init_vault_from_factory_params = list(init_vault_from_factory_params)
    old_deposit_asset_address = init_vault_from_factory_params[2]
    init_vault_from_factory_params[2] = NULL_ADDRESS
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    init_vault_from_factory_params[2] = old_deposit_asset_address


def test_create_strategy_with_null_buy_asset_address(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    init_vault_from_factory_params = list(init_vault_from_factory_params)
    old_buy_asset_address = init_vault_from_factory_params[3][0]
    init_vault_from_factory_params[3][0] = NULL_ADDRESS
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    init_vault_from_factory_params[3][0] = old_buy_asset_address


def test_buy_asset_list_contains_deposit_asset(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    init_vault_from_factory_params = list(init_vault_from_factory_params)
    old_buy_asset_address = init_vault_from_factory_params[3][0]
    init_vault_from_factory_params[3][0] = init_vault_from_factory_params[2]
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    init_vault_from_factory_params[3][0] = old_buy_asset_address


def test_create_strategy_with_invalid_swap_path_for_buy_token(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    init_vault_from_factory_params = list(init_vault_from_factory_params)
    old_buy_asset_address = init_vault_from_factory_params[3][0]
    init_vault_from_factory_params[3][0] = configs["token_not_paired_with_weth_address"]
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    init_vault_from_factory_params[3][0] = old_buy_asset_address


def test_create_strategy_with_invalid_swap_path_for_deposit_token(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    init_vault_from_factory_params = list(init_vault_from_factory_params)
    old_deposit_asset_address = init_vault_from_factory_params[2]
    init_vault_from_factory_params[2] = configs["token_not_paired_with_weth_address"]
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    init_vault_from_factory_params[2] = old_deposit_asset_address


def test_create_strategy_with_different_length_for_buy_tokens_and_percentages(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    strategy_params = list(strategy_params)
    old_buy_percentages = strategy_params[0]
    strategy_params[0] = [strategy_params[0][1]]
    # Act / Assert
    assert len(strategy_params[0]) != len(init_vault_from_factory_params[3])
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    strategy_params[0] = old_buy_percentages


def test_create_strategy_with_to_many_buy_tokens(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    init_vault_from_factory_params = list(init_vault_from_factory_params)
    old_buy_token_addresses = init_vault_from_factory_params[3]
    init_vault_from_factory_params[3] = configs["too_many_buy_token_addresses"]
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    init_vault_from_factory_params[3] = old_buy_token_addresses


def test_create_strategy_with_sum_of_buy_percentages_gt_100(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    strategy_params = list(strategy_params)
    old_buy_token_percentages = strategy_params[0]
    strategy_params[0] = [10_000, 10_000]  # 100%, 100%
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    strategy_params[0] = old_buy_token_percentages


def test_create_strategy_with_buy_percentage_eq_zero(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    strategy_params = list(strategy_params)
    old_buy_token_percentages = strategy_params[0]
    strategy_params[0] = [0, 10_000]  # 0%, 100%
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    strategy_params[0] = old_buy_token_percentages


def test_create_strategy_with_buy_percentage_lt_zero(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    strategy_params = list(strategy_params)
    old_deposit_token_address = strategy_params[2]
    strategy_params[0] = [-1, 10_000]  # -1%, 100%
    # Act / Assert
    with pytest.raises(OverflowError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    strategy_params[2] = old_deposit_token_address


def test_create_strategy_with_not_whitelisted_asset(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    init_vault_from_factory_params = list(init_vault_from_factory_params)
    old_deposit_asset_address = init_vault_from_factory_params[2]
    init_vault_from_factory_params[2] = configs["not_whitelisted_token_address_example"]
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    init_vault_from_factory_params[2] = old_deposit_asset_address


def test_create_strategy_with_deactivated_deposit_asset(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    strategy_manager = StrategyManager[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    init_vault_from_factory_params = list(init_vault_from_factory_params)
    old_deposit_asset_address = init_vault_from_factory_params[2]
    init_vault_from_factory_params[2] = configs["not_whitelisted_token_address_example"]
    # Act / Assert
    strategy_manager.deactivateWhitelistedDepositAsset(
        configs["whitelisted_deposit_assets"][4][0], {"from": dev_wallet}
    )
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    # Return to old state:
    init_vault_from_factory_params[2] = old_deposit_asset_address
    deposit_asset_to_whitelist = configs["whitelisted_deposit_assets"][4]
    strategy_manager.addWhitelistedDepositAssets([deposit_asset_to_whitelist], {"from": dev_wallet})


def test_create_strategy_exceeding_max_number_of_actions(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    strategy_params = list(strategy_params)
    old_buy_token_percentages = strategy_params[0]
    strategy_params[0] = [50, 50]  # 0.5%, 0.5% -> 100 Actions
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    strategy_params[0] = old_buy_token_percentages


def test_negative_value_deposit():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    # Act / Assert
    with pytest.raises(OverflowError):
        strategy_vault.deposit(-1, dev_wallet.address, {"from": dev_wallet})


def test_deposit_gt_deposit_token_balance():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        strategy_vault.deposit(GT_BALANCE_TESTING_VALUE, dev_wallet.address, {"from": dev_wallet})


def test_deposit_lt_min_deposit_value(configs, deposit_token, gas_price):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    vaults_factory.createVault(
        init_vault_from_factory_params,
        strategy_params,
        DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
        {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"], "gas_price": gas_price},
    )
    strategy_vault3 = get_strategy_vault(2)
    deposit_token.approve(
        strategy_vault3.address,
        DEV_WALLET_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT,
        {"from": dev_wallet2},
    )
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        strategy_vault3.deposit(1, dev_wallet.address, {"from": dev_wallet})


def test_negative_value_withdraw():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault2 = get_strategy_vault(1)
    # Act / Assert
    with pytest.raises(OverflowError):
        strategy_vault2.withdraw(NEGATIVE_AMOUNT_TESTING_VALUE, dev_wallet2, dev_wallet2, {"from": dev_wallet2})


def test_withdraw_gt_deposited_balance():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault2 = get_strategy_vault(1)
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        strategy_vault2.withdraw(GT_BALANCE_TESTING_VALUE, dev_wallet2, dev_wallet2, {"from": dev_wallet2})


def test_create_strategy_with_invalid_buy_frequency_enum_value(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    strategy_params = list(strategy_params)
    old_buy_frequency_enum_value = strategy_params[1]
    strategy_params[1] = 99
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    strategy_params[1] = old_buy_frequency_enum_value


def test_create_strategy_with_null_strategy_worker_address(configs):
    check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    strategy_params = list(strategy_params)
    old_buy_frequency_enum_value = strategy_params[2]
    strategy_params[2] = NULL_ADDRESS
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            DEV_WALLET_DEPOSIT_TOKEN_AMOUNT,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    strategy_params[2] = old_buy_frequency_enum_value


def test_set_last_update_by_not_worker_address():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        strategy_vault.setLastUpdatePerDepositor(dev_wallet, {"from": dev_wallet})


def test_get_all_vaults_with_start_after_equal_to_vault_length():
    vaults_factory = AutomatedVaultsFactory[-1]
    n_vaults = vaults_factory.allVaultsLength()
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults = vaults_factory.getBatchVaults(1, n_vaults)


def test_get_all_vaults_with_start_after_bigger_than_vault_length():
    vaults_factory = AutomatedVaultsFactory[-1]
    n_vaults = vaults_factory.allVaultsLength()
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.getBatchVaults(1, n_vaults + 1)


def test_get_all_depositors_with_start_after_equal_to_length():
    check_network_is_mainnet_fork()
    # Vaults have been created in previous tests.
    vault = get_strategy_vault()
    depositors_len = vault.allDepositorsLength()
    with pytest.raises(exceptions.VirtualMachineError):
        vault.getBatchDepositorAddresses(0, depositors_len)


def test_get_all_depositors_with_start_after_bigger_than_length():
    check_network_is_mainnet_fork()
    # Vaults have been created in previous tests.
    vault = get_strategy_vault()
    depositors_len = vault.allDepositorsLength()
    with pytest.raises(exceptions.VirtualMachineError):
        vault.getBatchDepositorAddresses(1, depositors_len + 1)


def test_transfer_ether_to_vault(deposit_token):
    vault = get_strategy_vault()
    with pytest.raises(exceptions.VirtualMachineError):
        dev_wallet.transfer(vault.address, Wei("0.0001 ether"))


################################ Helper Functions ################################


def __get_default_strategy_and_init_vault_params(configs: dict) -> Tuple[Tuple, Tuple]:
    worker_address = StrategyWorker[-1].address
    strategy_manager = StrategyManager[-1].address
    init_vault_from_factory_params = (
        configs["vault_name"],
        configs["vault_symbol"],
        configs["deposit_token_address"],
        configs["buy_token_addresses"],
    )
    strategy_params = (configs["buy_percentages"], configs["buy_frequency"], worker_address, strategy_manager)
    return strategy_params, init_vault_from_factory_params


def __get_init_vault_params(configs: dict, wallet_address: str) -> tuple:
    return (
        configs["vault_name"],
        configs["vault_symbol"],
        TreasuryVault[-1].address,
        wallet_address,
        AutomatedVaultsFactory[-1].address,
        False,
        configs["deposit_token_address"],
        configs["buy_token_addresses"],
        configs["creator_percentage_fee_on_deposit"],
        configs["treasury_percentage_fee_on_balance_update"],
    )
