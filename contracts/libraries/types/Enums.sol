// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

library Enums {
    enum BuyFrequency {
        FIFTEEN_MIN, //TEST ONLY -> TODO: DELETE BEFORE PROD DEPLOYMENT
        DAILY,
        WEEKLY,
        BI_WEEKLY,
        MONTHLY
    }
}
