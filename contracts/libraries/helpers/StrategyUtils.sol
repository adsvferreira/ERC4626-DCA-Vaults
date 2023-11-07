// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

/**
 * @title   Strategy Utils
 * @author  Pulsar Finance
 * @dev     VERSION: 1.0
 *          DATE:    2023.10.05
 */

import {Errors} from "../types/Errors.sol";
import {PercentageMath} from "../math/PercentageMath.sol";

library StrategyUtils {
    function buyPercentagesSum(
        uint256[] memory buyPercentages
    ) internal pure returns (uint256 sumOfBuyPercentages) {
        for (uint256 i; i < buyPercentages.length; ) {
            // No need to check if its smaller than 0 because it's an uint. Saves gas.
            if (buyPercentages[i] == 0) {
                revert Errors.InvalidParameters(
                    "Buy percentage must be gt zero"
                );
            }
            sumOfBuyPercentages += buyPercentages[i];
            unchecked {
                ++i;
            }
        }
    }
}
