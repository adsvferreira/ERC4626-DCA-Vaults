import pytest
from brownie import TreasuryVault, exceptions
from helpers import get_account_from_pk, check_network_is_mainnet_fork

dev_wallet = get_account_from_pk(1)
dev_wallet2 = get_account_from_pk(2)

DEV_WALLET_NATIVE_AMOUNT_TO_SEND = 1
DEV_WALLET_ERC20_AMOUNT_TO_SEND = 1
DEV_WALLET_NATIVE_AMOUNT_TO_WITHDRAW = 1
DEV_WALLET_ERC20_AMOUNT_TO_WITHDRAW = 1

NEGATIVE_AMOUNT_TESTING_VALUE = -1

################################ Contract Actions ################################


def test_send_ether_to_vault():
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    treasury_vault_address = treasury_vault.address
    initial_treasury_vault_native_balance = treasury_vault.balance()
    # Act
    dev_wallet.transfer(treasury_vault_address, f"{DEV_WALLET_NATIVE_AMOUNT_TO_SEND} wei")
    final_treasury_vault_native_balance = treasury_vault.balance()
    # Assert
    assert (
        final_treasury_vault_native_balance - initial_treasury_vault_native_balance == DEV_WALLET_NATIVE_AMOUNT_TO_SEND
    )


def test_send_erc20_to_treasury_vault(deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    treasury_vault_address = treasury_vault.address
    initial_treasury_vault_deposit_token_balance = deposit_token.balanceOf(treasury_vault_address)
    # Act
    deposit_token.transfer(treasury_vault_address, DEV_WALLET_ERC20_AMOUNT_TO_SEND, {"from": dev_wallet})
    final_treasury_vault_deposit_token_balance = deposit_token.balanceOf(treasury_vault_address)
    # Assert
    assert (
        final_treasury_vault_deposit_token_balance - initial_treasury_vault_deposit_token_balance
        == DEV_WALLET_ERC20_AMOUNT_TO_SEND
    )


def test_deposit_erc20(deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    treasury_vault_address = treasury_vault.address
    initial_treasury_vault_deposit_token_balance = deposit_token.balanceOf(treasury_vault_address)
    # Act
    deposit_token.approve(treasury_vault_address, DEV_WALLET_ERC20_AMOUNT_TO_SEND, {"from": dev_wallet})
    treasury_vault.depositERC20(DEV_WALLET_ERC20_AMOUNT_TO_SEND, deposit_token.address, {"from": dev_wallet})
    final_treasury_vault_deposit_token_balance = deposit_token.balanceOf(treasury_vault_address)
    # Assert
    assert (
        final_treasury_vault_deposit_token_balance - initial_treasury_vault_deposit_token_balance
        == DEV_WALLET_ERC20_AMOUNT_TO_SEND
    )


def test_withdraw_native_by_owner():
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    initial_treasury_vault_native_balance = treasury_vault.balance()
    # Act
    treasury_vault.withdrawNative(DEV_WALLET_NATIVE_AMOUNT_TO_WITHDRAW, {"from": dev_wallet})
    final_treasury_vault_native_balance = treasury_vault.balance()
    # Assert
    assert (
        initial_treasury_vault_native_balance - final_treasury_vault_native_balance
        == DEV_WALLET_NATIVE_AMOUNT_TO_WITHDRAW
    )


def test_withdraw_erc20_by_owner(deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    treasury_vault_address = treasury_vault.address
    initial_treasury_vault_deposit_token_balance = deposit_token.balanceOf(treasury_vault_address)
    # Act
    treasury_vault.withdrawERC20(deposit_token.address, DEV_WALLET_ERC20_AMOUNT_TO_WITHDRAW, {"from": dev_wallet})
    final_treasury_vault_deposit_token_balance = deposit_token.balanceOf(treasury_vault_address)
    # Assert
    assert (
        initial_treasury_vault_deposit_token_balance - final_treasury_vault_deposit_token_balance
        == DEV_WALLET_ERC20_AMOUNT_TO_WITHDRAW
    )


def test_withdraw_native_amount_eq_zero_by_owner():
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    initial_treasury_vault_native_balance = treasury_vault.balance()
    # Act
    treasury_vault.withdrawNative(0, {"from": dev_wallet})
    final_treasury_vault_native_balance = treasury_vault.balance()
    # Assert
    assert initial_treasury_vault_native_balance == final_treasury_vault_native_balance


def test_withdraw_erc20_amount_eq_zero_by_owner(deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    treasury_vault_address = treasury_vault.address
    initial_treasury_vault_deposit_token_balance = deposit_token.balanceOf(treasury_vault_address)
    # Act
    treasury_vault.withdrawERC20(deposit_token.address, 0, {"from": dev_wallet})
    final_treasury_vault_deposit_token_balance = deposit_token.balanceOf(treasury_vault_address)
    # Assert
    assert initial_treasury_vault_deposit_token_balance == final_treasury_vault_deposit_token_balance


################################ Contract Validations ################################


def test_withdraw_native_by_non_owner():
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        treasury_vault.withdrawNative(DEV_WALLET_NATIVE_AMOUNT_TO_WITHDRAW, {"from": dev_wallet2})


def test_withdraw_erc20_by_non_owner(deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        treasury_vault.withdrawERC20(deposit_token.address, DEV_WALLET_ERC20_AMOUNT_TO_WITHDRAW, {"from": dev_wallet2})


def test_withdraw_native_amount_gt_total_balance_by_owner():
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    treasury_vault_native_balance = treasury_vault.balance()
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        treasury_vault.withdrawNative(treasury_vault_native_balance + 1, {"from": dev_wallet})


def test_withdraw_erc20_amount_gt_total_balance_by_owner(deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    treasury_vault_address = treasury_vault.address
    treasury_vault_deposit_token_balance = deposit_token.balanceOf(treasury_vault_address)
    # Act / Assert
    with pytest.raises(exceptions.VirtualMachineError):
        treasury_vault.withdrawERC20(
            deposit_token.address, treasury_vault_deposit_token_balance + 1, {"from": dev_wallet}
        )


def test_withdraw_native_amount_lt_zero_by_owner():
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    # Act / Assert
    with pytest.raises(OverflowError):
        treasury_vault.withdrawNative(NEGATIVE_AMOUNT_TESTING_VALUE, {"from": dev_wallet})


def test_withdraw_erc20_amount_lt_zero_by_owner(deposit_token):
    check_network_is_mainnet_fork()
    # Arrange
    treasury_vault = TreasuryVault[-1]
    # Act / Assert
    with pytest.raises(OverflowError):
        treasury_vault.withdrawERC20(deposit_token.address, NEGATIVE_AMOUNT_TESTING_VALUE, {"from": dev_wallet})
