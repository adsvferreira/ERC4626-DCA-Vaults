import pytest
from typing import Tuple
from helpers import get_account_from_pk, check_network_is_mainnet_fork, get_strategy_vault, perc_mul_contracts_simulate
from scripts.deploy import (
    deploy_treasury_vault,
    deploy_controller,
    deploy_strategy_worker,
    deploy_automated_vaults_factory,
)
from brownie import (
    AutomatedVaultERC4626,
    AutomatedVaultsFactory,
    TreasuryVault,
    StrategyWorker,
    network,
    config,
    Contract,
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

DEV_WALLET_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT = 9_999_999_999_999_999_999
DEV_WALLET_DEPOSIT_TOKEN_AMOUNT = 20_000
DEV_WALLET2_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT = 9_999_999_999_999_999_999
DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT = 20_000
DEV_WALLET_WITHDRAW_TOKEN_AMOUNT = 10_000

NULL_ADDRESS = "0x0000000000000000000000000000000000000000"

################################ Contract Actions ################################


def test_create_new_vault(configs, deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    verify_flag = config["networks"][network.show_active()]["verify"]
    wallet_initial_native_balance = dev_wallet.balance()
    # Act
    treasury_vault = deploy_treasury_vault(dev_wallet, verify_flag)
    treasury_address = treasury_vault.address
    controller = deploy_controller(dev_wallet, verify_flag)
    controller_address = controller.address
    deploy_strategy_worker(
        dev_wallet,
        verify_flag,
        configs["dex_router_address"],
        configs["dex_main_token_address"],
        controller_address,
    )
    vaults_factory = deploy_automated_vaults_factory(
        dev_wallet,
        verify_flag,
        configs["dex_factory_address"],
        configs["dex_main_token_address"],
        treasury_address,
        configs["treasury_fixed_fee_on_vault_creation"],
        configs["creator_percentage_fee_on_deposit"],
        configs["treasury_percentage_fee_on_balance_update"],
    )
    treasury_vault_initial_native_balance = treasury_vault.balance()
    treasury_vault_initial_erc20_balance = deposit_token.balanceOf(treasury_address)
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    vaults_factory.createVault(
        init_vault_from_factory_params,
        strategy_params,
        {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
    )
    treasury_vault_final_native_balance = treasury_vault.balance()
    treasury_vault_final_erc20_balance = deposit_token.balanceOf(treasury_address)
    wallet_final_native_balance = dev_wallet.balance()
    native_token_fee_paid = (
        wallet_initial_native_balance - wallet_final_native_balance
    )  # gas price is 0 in local forked testnet
    # Assert
    assert vaults_factory.allVaultsLength() == 1
    assert bool(vaults_factory.getUserVaults(dev_wallet, 0))
    assert treasury_vault_initial_native_balance == 0
    assert treasury_vault_initial_erc20_balance == 0
    assert treasury_vault_final_native_balance == configs["treasury_fixed_fee_on_vault_creation"]
    assert treasury_vault_final_erc20_balance == 0  # Only native token fee on creation
    assert native_token_fee_paid == configs["treasury_fixed_fee_on_vault_creation"]


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
    assert name == configs["vault_name"]
    assert symbol == configs["vault_symbol"]
    assert treasury_address == TreasuryVault[-1].address
    assert dev_wallet == creator_address
    assert factory_address == AutomatedVaultsFactory[-1].address
    assert is_active == False  # No deposit yet
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
        strategy_type,
        _,
    ) = strategy_vault.getStrategyParams()
    # Act
    # Assert
    assert buy_percentages == configs["buy_percentages"]
    assert buy_frequency == configs["buy_frequency"]
    assert strategy_type == configs["strategy_type"]


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


def test_deposit_owned_vault(configs, deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_vault_lp_supply = strategy_vault.totalSupply()
    initial_vault_depositors_list_length = strategy_vault.allDepositorsLength()
    initial_vault_is_active = strategy_vault.getInitMultiAssetVaultParams()[5]
    initial_initial_wallet_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet)
    initial_wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet)
    expected_final_wallet_buy_amounts = [
        perc_mul_contracts_simulate(DEV_WALLET_DEPOSIT_TOKEN_AMOUNT, buy_perc)
        for buy_perc in configs["buy_percentages"]
    ]
    # Act
    deposit_token.approve(
        strategy_vault.address,
        DEV_WALLET_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT,
        {"from": dev_wallet},
    )
    strategy_vault.deposit(DEV_WALLET_DEPOSIT_TOKEN_AMOUNT, dev_wallet.address, {"from": dev_wallet})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_vault_lp_supply = strategy_vault.totalSupply()
    final_vault_depositors_list_length = strategy_vault.allDepositorsLength()
    depositor_address = strategy_vault.allDepositorAddresses(0)
    final_vault_is_active = strategy_vault.getInitMultiAssetVaultParams()[5]
    final_initial_wallet_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet)
    final_wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet)
    # Assert
    assert initial_wallet_lp_balance == 0
    assert initial_vault_lp_supply == 0
    assert initial_vault_depositors_list_length == 0
    assert initial_initial_wallet_deposit_balance == 0
    assert initial_wallet_buy_amounts == []
    assert final_wallet_lp_balance == DEV_WALLET_DEPOSIT_TOKEN_AMOUNT  # Ratio 1:1 lp token/ underlying token
    assert final_vault_lp_supply == DEV_WALLET_DEPOSIT_TOKEN_AMOUNT
    assert final_vault_depositors_list_length == 1
    assert depositor_address == dev_wallet
    assert initial_vault_is_active == False
    assert final_vault_is_active == True
    assert final_initial_wallet_deposit_balance == DEV_WALLET_DEPOSIT_TOKEN_AMOUNT
    assert final_wallet_buy_amounts == expected_final_wallet_buy_amounts


def test_deposit_not_owned_vault(configs, deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_wallet2_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    initial_vault_lp_supply = strategy_vault.totalSupply()
    initial_initial_wallet_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet)
    initial_wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet)
    initial_initial_wallet2_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet2)
    initial_wallet2_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet2)
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
    strategy_vault.deposit(DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT, dev_wallet2.address, {"from": dev_wallet2})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_wallet2_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    final_vault_lp_supply = strategy_vault.totalSupply()
    final_vault_depositors_list_length = strategy_vault.allDepositorsLength()
    second_depositor_address = strategy_vault.allDepositorAddresses(1)
    final_initial_wallet_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet)
    final_wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet)
    final_initial_wallet2_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet2)
    final_wallet2_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet2)
    # Assert
    assert initial_wallet2_lp_balance == 0
    assert initial_initial_wallet2_deposit_balance == 0
    assert initial_wallet2_buy_amounts == []
    assert final_vault_lp_supply == initial_vault_lp_supply + DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT
    assert final_vault_depositors_list_length == 2
    assert second_depositor_address == dev_wallet2
    assert (
        final_wallet2_lp_balance == DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT - creator_fee_on_deposit
    )  # Ratio 1:1 lp token/ underlying token
    assert (
        final_wallet_lp_balance == initial_wallet_lp_balance + creator_fee_on_deposit
    )  # Ratio 1:1 lp token/ underlying token
    assert initial_initial_wallet_deposit_balance == final_initial_wallet_deposit_balance
    assert initial_wallet_buy_amounts == final_wallet_buy_amounts
    assert final_initial_wallet2_deposit_balance == DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT - creator_fee_on_deposit
    assert final_wallet2_buy_amounts == expected_final_wallet2_buy_amounts


def test_partial_withdraw():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_vault_lp_supply = strategy_vault.totalSupply()
    # Act
    strategy_vault.withdraw(DEV_WALLET_WITHDRAW_TOKEN_AMOUNT, dev_wallet, dev_wallet, {"from": dev_wallet})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_vault_lp_supply = strategy_vault.totalSupply()
    # Assert
    assert final_vault_lp_supply == initial_vault_lp_supply - DEV_WALLET_WITHDRAW_TOKEN_AMOUNT
    assert (
        final_wallet_lp_balance == initial_wallet_lp_balance - DEV_WALLET_WITHDRAW_TOKEN_AMOUNT
    )  # Ratio 1:1 lp token/ underlying token


def test_total_withdraw():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_vault_lp_supply = strategy_vault.totalSupply()
    # Act
    strategy_vault.withdraw(initial_wallet_lp_balance, dev_wallet, dev_wallet, {"from": dev_wallet})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_vault_lp_supply = strategy_vault.totalSupply()
    # Assert
    assert final_vault_lp_supply == initial_vault_lp_supply - initial_wallet_lp_balance
    assert final_wallet_lp_balance == 0


def test_balance_of_creator_without_deposit_after_another_wallet_deposit(configs, deposit_token):
    check_network_is_mainnet_fork()
    # Arrange/Act
    vaults_factory = AutomatedVaultsFactory[-1]
    (
        strategy_params,
        init_vault_from_factory_params,
    ) = __get_default_strategy_and_init_vault_params(configs)
    vaults_factory.createVault(
        init_vault_from_factory_params,
        strategy_params,
        {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
    )
    strategy_vault = get_strategy_vault(index=1)
    initial_wallet2_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    initial_vault_lp_supply = strategy_vault.totalSupply()
    initial_vault_depositors_list_length = strategy_vault.allDepositorsLength()
    creator_fee_on_deposit = perc_mul_contracts_simulate(
        DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT, configs["creator_percentage_fee_on_deposit"]
    )
    initial_vault_is_active = strategy_vault.getInitMultiAssetVaultParams()[5]
    initial_initial_wallet_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet)
    initial_wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet)
    initial_initial_wallet2_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet2)
    initial_wallet2_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet2)
    expected_final_wallet_buy_amounts = [
        perc_mul_contracts_simulate(creator_fee_on_deposit, buy_perc) for buy_perc in configs["buy_percentages"]
    ]
    expected_final_wallet2_buy_amounts = [
        perc_mul_contracts_simulate(DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT - creator_fee_on_deposit, buy_perc)
        for buy_perc in configs["buy_percentages"]
    ]
    deposit_token.approve(
        strategy_vault.address,
        DEV_WALLET2_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT,
        {"from": dev_wallet2},
    )
    strategy_vault.deposit(DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT, dev_wallet2.address, {"from": dev_wallet2})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_wallet2_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    final_vault_lp_supply = strategy_vault.totalSupply()
    final_vault_depositors_list_length = strategy_vault.allDepositorsLength()
    first_depositor_address = strategy_vault.allDepositorAddresses(0)
    final_vault_is_active = strategy_vault.getInitMultiAssetVaultParams()[5]
    final_initial_wallet_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet)
    final_wallet_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet)
    final_initial_wallet2_deposit_balance = strategy_vault.getInitialDepositBalance(dev_wallet2)
    final_wallet2_buy_amounts = strategy_vault.getDepositorBuyAmounts(dev_wallet2)
    # Assert
    assert initial_vault_depositors_list_length == 0
    assert initial_wallet2_lp_balance == 0
    assert initial_initial_wallet_deposit_balance == 0
    assert initial_initial_wallet2_deposit_balance == 0
    assert initial_wallet_buy_amounts == []
    assert initial_wallet2_buy_amounts == []
    assert final_vault_lp_supply == initial_vault_lp_supply + DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT
    assert final_vault_depositors_list_length == 2  # Depositor + creator that received fee as lp token
    assert first_depositor_address == dev_wallet2
    assert (
        final_wallet2_lp_balance == DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT - creator_fee_on_deposit
    )  # Ratio 1:1 lp token/ underlying token
    assert final_wallet_lp_balance == creator_fee_on_deposit  # Ratio 1:1 lp token/ underlying token
    assert initial_vault_is_active == False
    assert final_vault_is_active == True
    assert final_initial_wallet2_deposit_balance == DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT - creator_fee_on_deposit
    assert final_wallet2_buy_amounts == expected_final_wallet2_buy_amounts
    assert final_initial_wallet_deposit_balance == creator_fee_on_deposit
    assert final_wallet_buy_amounts == expected_final_wallet_buy_amounts


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
    strategy_params[0] = [0, 10_000]  # 100%, 100%
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
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
    old_buy_token_percentages = strategy_params[0]
    strategy_params[0] = [-1, 10_000]  # 100%, 100%
    # Act / Assert
    with pytest.raises(OverflowError):
        vaults_factory.createVault(
            init_vault_from_factory_params,
            strategy_params,
            {"from": dev_wallet, "value": configs["treasury_fixed_fee_on_vault_creation"]},
        )
    strategy_params[0] = old_buy_token_percentages


def test_set_last_update_by_not_worker_address():
    check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = get_strategy_vault()
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        strategy_vault.setLastUpdatePerDepositor(dev_wallet, {"from": dev_wallet})


################################ Helper Functions ################################


def __get_default_strategy_and_init_vault_params(configs: dict) -> Tuple[Tuple, Tuple]:
    worker_address = StrategyWorker[-1].address
    init_vault_from_factory_params = (
        configs["vault_name"],
        configs["vault_symbol"],
        configs["deposit_token_address"],
        configs["buy_token_addresses"],
    )
    strategy_params = (
        configs["buy_percentages"],
        configs["buy_frequency"],
        configs["strategy_type"],
        worker_address,
    )
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


# TODO: Add test for sum buy percentages > 0
