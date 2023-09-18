// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

import {ConfigTypes} from "../libraries/types/ConfigTypes.sol";

interface IStrategyWorker {
    function executeStrategyAction(
        address _strategyVaultAddress,
        address _depositorAddress
    ) external;
}
