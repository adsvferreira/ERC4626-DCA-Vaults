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
    IAutomatedVaultsFactory public automatedVaultsFactory;

    address public strategyWorkerAddress;

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
        address[] memory allVaults = automatedVaultsFactory
            .getAllVaultsPerStrategyWorker(strategyWorkerAddress);
        bool canExec;
        bytes memory execPayload;
        uint256 allVaultsLength = allVaults.length;

        for (uint256 i; i < allVaultsLength; ) {
            AutomatedVaultERC4626 vault = AutomatedVaultERC4626(allVaults[i]);
            uint256 _vaulDepositorsLength = vault.allDepositorsLength();
            for (uint256 j; j < _vaulDepositorsLength; ) {
                execPayload = abi.encodeWithSelector(
                    IController.triggerStrategyAction.selector,
                    strategyWorkerAddress,
                    address(vault),
                    vault.getDepositorAddress(j)
                );

                canExec = _canExec(
                    vault.lastUpdateOf(vault.getDepositorAddress(j)),
                    vault.getUpdateFrequencyTimestamp(),
                    vault.balanceOf(vault.getDepositorAddress(j)),
                    vault.getDepositorTotalPeriodicBuyAmount(
                        vault.getDepositorAddress(j)
                    )
                );

                if (canExec) {
                    return (canExec, execPayload);
                }
                unchecked {
                    ++j;
                }
            }
            unchecked {
                ++i;
            }
        }
        return (canExec, execPayload);
    }

    function _canExec(
        uint256 lastUpdateOf,
        uint256 updateFrequencyTimestamp,
        uint256 depositorBalance,
        uint256 depositorTotalPeriodicBuyAmount
    ) private view returns (bool) {
        return (((block.timestamp >=
            (lastUpdateOf + updateFrequencyTimestamp)) || lastUpdateOf == 0) &&
            (depositorBalance >= depositorTotalPeriodicBuyAmount));
    }
}
