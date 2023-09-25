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
    mapping(address => bool) public whitelistedCallers;

    constructor() {
        whitelistedCallers[msg.sender] = true;
    }

    // Only Callable by Pulsar Deployer EOA Address (Owner) or Gelato Dedicated msg.sender
    modifier onlyWhitelisted() {
        require(whitelistedCallers[msg.sender], "FORBIDDEN");
        _;
    }

    function triggerStrategyAction(
        address strategyWorkerAddress,
        address strategyVaultAddress,
        address depositorAddress
    ) external onlyWhitelisted {
        IStrategyWorker strategyWorker = IStrategyWorker(strategyWorkerAddress);
        strategyWorker.executeStrategyAction(
            strategyVaultAddress,
            depositorAddress
        );
    }

    function setWhitelistedCaller(
        address whitelistedCaller
    ) external onlyOwner {
        require(
            whitelistedCaller != address(0),
            "Null Address is not a valid whitelisted caller address"
        );
        whitelistedCallers[whitelistedCaller] = true;
    }

    function delWhitelistedCaller(
        address whitelistedCaller
    ) external onlyOwner {
        require(whitelistedCaller != owner(), "Owner cannot be removed");
        whitelistedCallers[whitelistedCaller] = false;
    }
}
