// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

/**
 * @title   Gelato Automate Resolver.
 * @author  André Ferreira
 * @dev    VERSION: 1.0
 *          DATE:    2023.09.20
 */

import {IController} from "../interfaces/IController.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";
import {AutomatedVaultERC4626} from "./AutomatedVaultERC4626.sol";
import {IAutomatedVaultsFactory} from "../interfaces/IAutomatedVaultsFactory.sol";

contract Resolver {
    IAutomatedVaultsFactory automatedVaultsFactory;

    address strategyWorkerAddress;

    constructor(
        address _automatedVaultsFactoryAddress,
        address _strategyWorkerAddress
    ) {
        automatedVaultsFactory = IAutomatedVaultsFactory(
            _automatedVaultsFactoryAddress
        );
        strategyWorkerAddress = _strategyWorkerAddress;
    }

    function checker() external view returns (bool, bytes memory) {
        uint256 allVaultsLength = automatedVaultsFactory.allVaultsLength();
        bool canExec;
        bytes memory execPayload;

        for (uint256 i = 0; i < allVaultsLength; i++) {
            AutomatedVaultERC4626 vault = AutomatedVaultERC4626(
                automatedVaultsFactory.getVaultAddress(i)
            );

            for (uint256 j = 0; j < vault.allDepositorsLength(); j++) {
                execPayload = abi.encodeWithSelector(
                    IController.triggerStrategyAction.selector,
                    strategyWorkerAddress,
                    address(vault),
                    vault.allDepositorAddresses(j)
                );

                canExec =
                    (block.timestamp >=
                        (vault.lastUpdateOf(vault.allDepositorAddresses(j)) +
                            vault.getUpdateFrequencyTimestamp())) ||
                    vault.lastUpdateOf(vault.allDepositorAddresses(j)) == 0;

                if (canExec) {
                    return (canExec, execPayload);
                }
            }
        }
        return (canExec, execPayload);
    }
}
