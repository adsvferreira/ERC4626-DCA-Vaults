// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

/**
 * @title   Strategy Controller.
 * @author  André Ferreira

  * @dev    VERSION: 1.0
 *          DATE:    2023.08.29
*/

import {IController} from "../interfaces/IController.sol";
import {IStrategyWorker} from "../interfaces/IStrategyWorker.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

contract Controller is IController, Ownable {
    // Only Callable by Pulsar Deployer EOA Address
    function triggerStrategyAction(
        address strategyWorkerAddress,
        address strategyVaultAddress,
        address depositorAddress
    ) external onlyOwner {
        IStrategyWorker strategyWorker = IStrategyWorker(strategyWorkerAddress);
        strategyWorker.executeStrategyAction(
            strategyVaultAddress,
            depositorAddress
        );
    }
}
