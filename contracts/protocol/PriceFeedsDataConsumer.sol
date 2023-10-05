// SPDX-License-Identifier: MIT
pragma solidity 0.8.21;

/**
 * @title   Price Feeds Data Consumer
 * @author  André Ferreira
 * @dev    VERSION: 1.0
 *          DATE:    2023.10.05
 */

import {AggregatorV3Interface} from "@chainlink/contracts/src/v0.8/interfaces/AggregatorV3Interface.sol";

contract PriceFeedsDataConsumer {
    AggregatorV3Interface nativeTokenDataFeed;

    constructor(address _nativeTokenOracleAddress) {
        nativeTokenDataFeed = AggregatorV3Interface(_nativeTokenOracleAddress);
    }

    function getDataFeedLatestPriceAndDecimals(
        address oracleAddress
    ) external view returns (int256, uint8) {
        AggregatorV3Interface dataFeed = AggregatorV3Interface(oracleAddress);
        // prettier-ignore
        (
            /* uint80 roundID */,
            int256 answer,
            /*uint256 startedAt*/,
            /*uint256 timeStamp*/,
            /*uint80 answeredInRound*/
        ) = dataFeed.latestRoundData();
        uint8 decimals = dataFeed.decimals();
        return (answer, decimals);
    }

    function getNativeTokenDataFeedLatestPriceAndDecimals()
        external
        view
        returns (int256, uint8)
    {
        // prettier-ignore
        (
            /* uint80 roundID */,
            int256 answer,
            /*uint256 startedAt*/,
            /*uint256 timeStamp*/,
            /*uint80 answeredInRound*/
        ) = nativeTokenDataFeed.latestRoundData();
        uint8 decimals = nativeTokenDataFeed.decimals();
        return (answer, decimals);
    }

    function getTokenDataFeedLatestPriceParsed(
        address oracleAddress
    ) external view returns (int256 tokenParsedPrice) {
        (int256 tokenPrice, uint8 tokenPriceDecimals) = this
            .getDataFeedLatestPriceAndDecimals(oracleAddress);
        require(
            tokenPriceDecimals > 0,
            "Price feed returned 0 for token decimals"
        );
        int8 castedTokenPriceDecimals = int8(tokenPriceDecimals);
        tokenParsedPrice = tokenPrice / int256(castedTokenPriceDecimals);
    }

    function getNativeTokenDataFeedLatestPriceParsed()
        external
        view
        returns (int256 nativeTokenParsedPrice)
    {
        (int256 nativeTokenPrice, uint8 nativeTokenPriceDecimals) = this
            .getNativeTokenDataFeedLatestPriceAndDecimals();
        require(
            nativeTokenPriceDecimals > 0,
            "Price feed returned 0 for native token decimals"
        );
        int8 castedNativeTokenPriceDecimals = int8(nativeTokenPriceDecimals);
        nativeTokenParsedPrice =
            nativeTokenPrice /
            int256(castedNativeTokenPriceDecimals);
    }
}
