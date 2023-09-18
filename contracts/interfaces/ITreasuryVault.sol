// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

interface ITreasuryVault {
    function withdrawNative(uint256 _amount) external;

    function depositERC20(uint256 _amount, address _asset) external;

    function withdrawERC20(address _tokenAddress, uint256 _amount) external;
}
