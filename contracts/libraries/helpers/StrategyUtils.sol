// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

/**
 * @title   Strategy Utils
 * @author  André Ferreira
 * @dev    VERSION: 1.0
 *          DATE:    2023.10.05
 */

import {PercentageMath} from "../math/PercentageMath.sol";

library StrategyUtils {
    /**
     * @dev Note: division by zero needs to be previously checked
     */
    function calculateStrategyMaxNumberOfActions(
        uint256 sumOfBuyPercentages
    ) internal pure returns (uint256 maxNumberOfActions) {
        maxNumberOfActions =
            PercentageMath.PERCENTAGE_FACTOR /
            sumOfBuyPercentages;
    }

    function buyPercentagesSum(
        uint256[] memory buyPercentages
    ) internal pure returns (uint256 sumOfBuyPercentages) {
        for (uint256 i = 0; i < buyPercentages.length; i++) {
            require(buyPercentages[i] > 0, "Buy percentage must be gt zero");
            sumOfBuyPercentages += buyPercentages[i];
        }
    }
}
