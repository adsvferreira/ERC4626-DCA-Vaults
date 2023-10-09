// SPDX-License-Identifier: MIT

pragma solidity 0.8.21;

import {Enums} from "./Enums.sol";

library Events {
    // AUTOMATED VAULT

    event CreatorFeeTransfered(
        address indexed vault,
        address indexed depositor,
        address indexed creator,
        uint256 shares
    );

    /**
     * @dev Attempted to deposit more assets than the max amount for `receiver`.
     */
    error ERC4626ExceededMaxDeposit(
        address receiver,
        uint256 assets,
        uint256 max
    );

    // VAULT FACTORY

    event VaultCreated(
        address indexed creator,
        address indexed depositAsset,
        address[] buyAssets,
        address vaultAddress,
        uint256[] buyPercentages,
        Enums.BuyFrequency buyFrequency
    );

    event TreasuryFeeTransfered(address creator, uint256 amount);

    // TREASURY VAULT

    event TreasuryCreated(address creator, address treasuryAddress);
    event EtherReceived(address indexed sender, uint256 amount);
    event ERC20Received(address indexed sender, uint256 amount, address asset);
    event NativeWithdrawal(address indexed owner, uint256 amount);
    event ERC20Withdrawal(
        address indexed owner,
        address indexed token,
        uint256 amount
    );
}
