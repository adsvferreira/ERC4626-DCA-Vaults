import pytest
from typing import List, Tuple
from docs.abis import erc20_abi
from helpers import get_account_from_pk
from scripts.deploy import deploy_treasury_vault, deploy_controller, deploy_strategy_worker, deploy_automated_vaults_factory
from brownie import AutomatedVaultERC4626, AutomatedVaultsFactory, TreasuryVault, StrategyWorker, network, config, Contract, exceptions, web3

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

DEV_WALLET_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT = 100_000
DEV_WALLET_DEPOSIT_TOKEN_AMOUNT = 20_000
DEV_WALLET2_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT = 100_000
DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT = 20_000
DEV_WALLET_WITHDRAW_TOKEN_AMOUNT = 10_000

@pytest.fixture()
def configs():
    __check_network_is_mainnet_fork()
    active_network_configs = config["networks"][network.show_active()]
    protocol_params = config["protocol-params"]
    strategy_params = config["strategy-params"]
    return {
        "dex_main_token_address":active_network_configs["dex_main_token_address"],
        "dex_router_address":active_network_configs["dex_router_address"],
        "dex_factory_address":active_network_configs["dex_factory_address"],
        "deposit_token_address":active_network_configs["deposit_token_address"],
        "buy_token_addresses":active_network_configs["buy_token_addresses"],
        "vault_name":active_network_configs["vault_name"],
        "vault_symbol":active_network_configs["vault_symbol"],
        "treasury_fixed_fee_on_vault_creation": protocol_params["treasury_fixed_fee_on_vault_creation"],
        "creator_percentage_fee_on_deposit": protocol_params["creator_percentage_fee_on_deposit"],
        "treasury_percentage_fee_on_balance_update": protocol_params["treasury_percentage_fee_on_balance_update"],
        "buy_amounts": strategy_params["buy_amounts"],
        "buy_frequency": strategy_params["buy_frequency"],
        "strategy_type": strategy_params["strategy_type"]
    }

@pytest.fixture()
def deposit_token():
    __check_network_is_mainnet_fork()
    return Contract.from_abi("ERC20", config["networks"][network.show_active()]["deposit_token_address"], erc20_abi)

################################ Contract Actions ################################ 

def test_create_new_vault(configs, deposit_token):
    __check_network_is_mainnet_fork()
    # Arrange
    verify_flag = config["networks"][network.show_active()]["verify"]
    wallet_initial_native_balance = dev_wallet.balance()
    # Act
    treasury_vault = deploy_treasury_vault(dev_wallet, verify_flag)
    treasury_address = treasury_vault.address
    controller = deploy_controller(dev_wallet, verify_flag)
    controller_address = controller.address
    deploy_strategy_worker(dev_wallet, verify_flag, configs["dex_router_address"], configs["dex_main_token_address"], controller_address)
    vaults_factory = deploy_automated_vaults_factory(dev_wallet, verify_flag, configs["dex_factory_address"], configs["dex_main_token_address"], treasury_address, configs["treasury_fixed_fee_on_vault_creation"], configs["creator_percentage_fee_on_deposit"], configs["treasury_percentage_fee_on_balance_update"])
    treasury_vault_initial_native_balance = treasury_vault.balance()
    treasury_vault_initial_erc20_balance = deposit_token.balanceOf(treasury_address)
    strategy_params, init_vault_from_factory_params = __get_default_strategy_and_init_vault_params(configs)
    vaults_factory.createVault(init_vault_from_factory_params, strategy_params, {'from':dev_wallet, "value":100_000_000_000_000})
    treasury_vault_final_native_balance = treasury_vault.balance()
    treasury_vault_final_erc20_balance = deposit_token.balanceOf(treasury_address)
    wallet_final_native_balance = dev_wallet.balance()
    native_token_fee_paid = wallet_initial_native_balance - wallet_final_native_balance # gas price is 0 in local forked testnet
    # Assert
    assert vaults_factory.allVaultsLength() == 1
    assert bool(vaults_factory.getUserVaults(dev_wallet,0))
    assert treasury_vault_initial_native_balance == 0
    assert treasury_vault_initial_erc20_balance == 0
    assert treasury_vault_final_native_balance == configs["treasury_fixed_fee_on_vault_creation"]
    assert treasury_vault_final_erc20_balance == 0 # Only native token fee on creation
    assert native_token_fee_paid == configs["treasury_fixed_fee_on_vault_creation"]

def test_created_vault_init_params(configs):
    __check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = __get_strategy_vault()    
    name, symbol, treasury_address, creator_address, factory_address, is_active, deposit_asset, buy_assets, creator_perc_fee, treasury_perc_fee = strategy_vault.getInitMultiAssetVaultParams()
    # Act
    # Assert
    assert name == configs["vault_name"]
    assert symbol == configs["vault_symbol"]
    assert treasury_address == TreasuryVault[-1].address
    assert dev_wallet == creator_address
    assert factory_address == AutomatedVaultsFactory[-1].address
    assert is_active == False # No deposit yet
    assert deposit_asset == configs["deposit_token_address"]
    assert buy_assets == configs["buy_token_addresses"]
    assert creator_perc_fee == configs["creator_percentage_fee_on_deposit"]
    assert treasury_perc_fee == configs["treasury_percentage_fee_on_balance_update"]

def test_created_vault_strategy_params(configs):
    __check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = __get_strategy_vault()
    buy_amounts, buy_frequency, strategy_type, strategy_worker = strategy_vault.getStrategyParams()
    # Act
    # Assert
    assert buy_amounts == configs["buy_amounts"]
    assert buy_frequency == configs["buy_frequency"]
    assert strategy_type == configs["strategy_type"]

def test_created_vault_buy_tokens(configs):
    __check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = __get_strategy_vault()   
    buy_token_addresses = strategy_vault.getBuyAssetAddresses()
    # Act
    # Assert
    assert strategy_vault.buyAssetsLength() == len(configs["buy_token_addresses"])
    assert buy_token_addresses == configs["buy_token_addresses"]
    assert __get_tokens_decimals(buy_token_addresses) == __get_vault_buy_token_decimals(strategy_vault)
    assert strategy_vault.asset() == configs["deposit_token_address"]

def test_deposit_owned_vault(deposit_token):
    __check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = __get_strategy_vault()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_vault_lp_supply = strategy_vault.totalSupply()
    initial_vault_depositors_list_length = strategy_vault.allDepositorsLength()
    # Act
    deposit_token.approve(strategy_vault.address, DEV_WALLET_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT, {'from': dev_wallet})
    strategy_vault.deposit(DEV_WALLET_DEPOSIT_TOKEN_AMOUNT, dev_wallet.address, {'from': dev_wallet})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_vault_lp_supply = strategy_vault.totalSupply()
    final_vault_depositors_list_length = strategy_vault.allDepositorsLength()    
    depositor_address = strategy_vault.allDepositorAddresses(0)
    # Assert
    assert initial_wallet_lp_balance == 0
    assert initial_vault_lp_supply == 0
    assert initial_vault_depositors_list_length == 0
    assert final_wallet_lp_balance == DEV_WALLET_DEPOSIT_TOKEN_AMOUNT # Ratio 1:1 lp token/ underlying token
    assert final_vault_lp_supply == DEV_WALLET_DEPOSIT_TOKEN_AMOUNT
    assert final_vault_depositors_list_length == 1
    assert depositor_address == dev_wallet

def test_deposit_not_owned_vault(configs, deposit_token):
    __check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = __get_strategy_vault()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_wallet2_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    initial_vault_lp_supply = strategy_vault.totalSupply()
    creator_percentage_fee_on_deposit = configs["creator_percentage_fee_on_deposit"] / 10_000
    creator_fee_on_deposit = creator_percentage_fee_on_deposit * DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT
    # Act
    deposit_token.approve(strategy_vault.address, DEV_WALLET2_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT, {'from': dev_wallet2})
    strategy_vault.deposit(DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT, dev_wallet2.address, {'from': dev_wallet2})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_wallet2_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    final_vault_lp_supply = strategy_vault.totalSupply()
    final_vault_depositors_list_length = strategy_vault.allDepositorsLength()    
    second_depositor_address = strategy_vault.allDepositorAddresses(1)
    # Assert
    assert initial_wallet2_lp_balance == 0
    assert final_vault_lp_supply == initial_vault_lp_supply + DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT
    assert final_vault_depositors_list_length == 2
    assert second_depositor_address == dev_wallet2
    assert final_wallet2_lp_balance == DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT - creator_fee_on_deposit # Ratio 1:1 lp token/ underlying token
    assert final_wallet_lp_balance == initial_wallet_lp_balance + creator_fee_on_deposit # Ratio 1:1 lp token/ underlying token

def test_partial_withdraw():
    __check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = __get_strategy_vault()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_vault_lp_supply = strategy_vault.totalSupply()
    # Act
    strategy_vault.withdraw(DEV_WALLET_WITHDRAW_TOKEN_AMOUNT, dev_wallet,dev_wallet, {'from': dev_wallet})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_vault_lp_supply = strategy_vault.totalSupply()
    # Assert
    assert final_vault_lp_supply == initial_vault_lp_supply - DEV_WALLET_WITHDRAW_TOKEN_AMOUNT
    assert final_wallet_lp_balance == initial_wallet_lp_balance - DEV_WALLET_WITHDRAW_TOKEN_AMOUNT # Ratio 1:1 lp token/ underlying token


def test_total_withdraw():
    __check_network_is_mainnet_fork()
    # Arrange
    strategy_vault = __get_strategy_vault()
    initial_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    initial_vault_lp_supply = strategy_vault.totalSupply()
    # Act
    strategy_vault.withdraw(initial_wallet_lp_balance, dev_wallet,dev_wallet, {'from': dev_wallet})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_vault_lp_supply = strategy_vault.totalSupply()
    # Assert
    assert final_vault_lp_supply == initial_vault_lp_supply - initial_wallet_lp_balance
    assert final_wallet_lp_balance == 0


def test_balance_of_creator_without_deposit_after_another_wallet_deposit(configs, deposit_token):
    __check_network_is_mainnet_fork()
    # Arrange
    vaults_factory = AutomatedVaultsFactory[-1]
    strategy_params, init_vault_from_factory_params = __get_default_strategy_and_init_vault_params(configs)
    vaults_factory.createVault(init_vault_from_factory_params, strategy_params, {'from':dev_wallet, "value":100_000_000_000_000})
    strategy_vault = __get_strategy_vault(index=1)
    initial_wallet2_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    initial_vault_lp_supply = strategy_vault.totalSupply()
    initial_vault_depositors_list_length = strategy_vault.allDepositorsLength()
    creator_percentage_fee_on_deposit = configs["creator_percentage_fee_on_deposit"] / 10_000
    creator_fee_on_deposit = creator_percentage_fee_on_deposit * DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT
    # Act
    deposit_token.approve(strategy_vault.address, DEV_WALLET2_DEPOSIT_TOKEN_ALLOWANCE_AMOUNT, {'from': dev_wallet2})
    strategy_vault.deposit(DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT, dev_wallet2.address, {'from': dev_wallet2})
    final_wallet_lp_balance = strategy_vault.balanceOf(dev_wallet)
    final_wallet2_lp_balance = strategy_vault.balanceOf(dev_wallet2)
    final_vault_lp_supply = strategy_vault.totalSupply()
    final_vault_depositors_list_length = strategy_vault.allDepositorsLength()  
    first_depositor_address = strategy_vault.allDepositorAddresses(0)
    # Assert
    assert initial_vault_depositors_list_length == 0
    assert initial_wallet2_lp_balance == 0
    assert final_vault_lp_supply == initial_vault_lp_supply + DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT
    assert final_vault_depositors_list_length == 2 # Depositor + creator that received fee as lp token
    assert first_depositor_address == dev_wallet2
    assert final_wallet2_lp_balance == DEV_WALLET2_DEPOSIT_TOKEN_AMOUNT - creator_fee_on_deposit # Ratio 1:1 lp token/ underlying token
    assert final_wallet_lp_balance == creator_fee_on_deposit # Ratio 1:1 lp token/ underlying token  




# TODO:    
#       1 - Add validation for buy_address != deposit address (+ tests)
#       2 - Remove deposit address after withdraw if zero address (+ add validation to test_total_withdraw)
#       3 - Adapt contracts for weth as deposit token (swap path)
#       4 - Test set last update when testing worker action


################################ Contract Validations ################################ 

def test_instantiate_strategy_from_non_factory_address(configs):
    # Arrange
    verify_flag = config["networks"][network.show_active()]["verify"]
    strategy_params, _ = __get_default_strategy_and_init_vault_params(configs)
    init_vault_params = __get_init_vault_params(configs, dev_wallet)
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        AutomatedVaultERC4626.deploy(init_vault_params, strategy_params, {'from': dev_wallet}, publish_source=verify_flag)        

def test_create_strategy_with_insufficient_ether_balance(configs):
    __check_network_is_mainnet_fork()
    # Arrange 
    vaults_factory = AutomatedVaultsFactory[-1]  
    strategy_params, init_vault_from_factory_params = __get_default_strategy_and_init_vault_params(configs)    
    # Act / Assert
    assert empty_wallet.balance() == 0
    with pytest.raises(ValueError):
        vaults_factory.createVault(init_vault_from_factory_params, strategy_params, {'from':empty_wallet, "value":100_000_000_000_000}) 

def test_create_strategy_with_null_deposit_asset_address():
    pass

def test_create_strategy_with_invalid_swap_path_for_buy_token():
    pass

def test_create_strategy_with_invalid_swap_path_for_deposit_token():
    pass

def test_create_strategy_with_different_length_for_buy_tokens_and_amounts():
    pass

def test_create_strategy_with_to_many_buy_tokens():
    pass

def test_deposit_with_null_deposit_asset_address():
    pass

def test_set_last_update_by_not_worker_address():
    pass



################################ Helper Functions ################################ 

def __check_network_is_mainnet_fork():
    if network.show_active() == "development" or "fork" not in network.show_active():
        pytest.skip("Only for mainnet-fork testing!")

def __get_default_strategy_and_init_vault_params(configs:dict) -> Tuple[Tuple, Tuple]:
    worker_address = StrategyWorker[-1].address
    init_vault_from_factory_params=(configs["vault_name"], configs["vault_symbol"], configs["deposit_token_address"], configs["buy_token_addresses"])
    strategy_params=(configs["buy_amounts"], configs["buy_frequency"], configs["strategy_type"], worker_address)
    return strategy_params, init_vault_from_factory_params

def __get_strategy_vault(index: int=0) -> AutomatedVaultERC4626:
    created_strategy_vault_address = AutomatedVaultsFactory[-1].allVaults(index)
    return AutomatedVaultERC4626.at(created_strategy_vault_address)

def __get_vault_buy_token_decimals(strategy_vault: AutomatedVaultERC4626) -> List[str]:
    return[strategy_vault.buyAssetsDecimals(i) for i in range(strategy_vault.buyAssetsLength())]

def __get_tokens_decimals(token_addresses: List[str]) -> int:
    return [Contract.from_abi("ERC20", token_address, erc20_abi).decimals() for token_address in token_addresses]

def __get_init_vault_params(configs:dict, wallet_address:str) -> tuple:
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
        configs["treasury_percentage_fee_on_balance_update"]
    )
