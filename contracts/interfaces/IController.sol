// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

interface IController {
    function triggerStrategyAction(
        address strategyWorkerAddress,
        address strategyVaultAddress,
        address depositorAddress
    ) external;

    function setWhitelistedCaller(address whitelistedCaller) external;

    function delWhitelistedCaller(address whitelistedCaller) external;
}
