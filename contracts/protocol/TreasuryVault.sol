// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

/**
 * @title   Strategy Vault.
 * @author  André Ferreira

  * @dev    VERSION: 1.0
 *          DATE:    2023.08.29
*/

import {ITreasuryVault} from "../interfaces/ITreasuryVault.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

contract TreasuryVault is ITreasuryVault, Ownable {
    using SafeERC20 for IERC20;

    event TreasuryCreated(address creator, address treasuryAddress);
    event EtherReceived(address indexed sender, uint256 amount);
    event ERC20Received(address indexed sender, uint256 amount, address asset);
    event NativeWithdrawal(address indexed owner, uint256 amount);
    event ERC20Withdrawal(
        address indexed owner,
        address indexed token,
        uint256 amount
    );

    constructor() {
        emit TreasuryCreated(msg.sender, address(this));
    }

    receive() external payable {
        emit EtherReceived(msg.sender, msg.value);
    }

    function withdrawNative(uint256 amount) external onlyOwner {
        require(amount <= address(this).balance, "Insufficient balance");
        (bool success, ) = owner().call{value: amount}("");
        require(success, "Ether transfer failed");
        emit NativeWithdrawal(owner(), amount);
    }

    function depositERC20(uint256 amount, address asset) external {
        IERC20(asset).safeTransferFrom(msg.sender, address(this), amount);
        emit ERC20Received(msg.sender, amount, asset);
    }

    function withdrawERC20(
        address tokenAddress,
        uint256 amount
    ) external onlyOwner {
        IERC20 token = IERC20(tokenAddress);
        require(
            amount <= token.balanceOf(address(this)),
            "Insufficient balance"
        );
        (bool success, ) = tokenAddress.call(
            abi.encodeWithSignature(
                "transfer(address,uint256)",
                owner(),
                amount
            )
        );
        require(success, "Token transfer failed");
        emit ERC20Withdrawal(owner(), tokenAddress, amount);
    }
}
