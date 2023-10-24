// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

/**
 * @title   Strategy Controller.
 * @author  Pulsar Finance
 * @dev     VERSION: 1.0
 *          DATE:    2023.08.29
 */

import {Roles} from "../libraries/roles/Roles.sol";
import {IController} from "../interfaces/IController.sol";
import {IStrategyWorker} from "../interfaces/IStrategyWorker.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

contract Controller is IController, AccessControl {
    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(Roles.CONTROLLER_CALLER, msg.sender);
    }

    function triggerStrategyAction(
        address strategyWorkerAddress,
        address strategyVaultAddress,
        address depositorAddress
    ) external onlyRole(Roles.CONTROLLER_CALLER) {
        IStrategyWorker strategyWorker = IStrategyWorker(strategyWorkerAddress);
        strategyWorker.executeStrategyAction(
            strategyVaultAddress,
            depositorAddress
        );
    }
}
