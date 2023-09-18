// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

interface IController {
    function triggerStrategyAction(
        address _strategyWorkerAddress,
        address _strategyVaultAddress,
        address _depositorAddress
    ) external;
}
