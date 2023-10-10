from helpers import (
    check_network_is_mainnet_fork,
)
from brownie import (
    PriceFeedsDataConsumer,
)

################################ Contract Actions ################################


def test_get_prices_for_all_whitelisted_addresses(configs):
    check_network_is_mainnet_fork()
    # Arrange
    price_feeds_data_consumer = PriceFeedsDataConsumer[-1]
    # Act/Assert
    for _, _, oracle_address, _ in configs["whitelisted-deposit-assets"]:
        token_price, token_price_decimals = price_feeds_data_consumer.getDataFeedLatestPriceAndDecimals(oracle_address)
        assert token_price > 0
        assert token_price_decimals > 0


def test_get_native_token_price():
    check_network_is_mainnet_fork()
    # Arrange
    price_feeds_data_consumer = PriceFeedsDataConsumer[-1]
    # Act
    (
        native_token_price,
        native_token_price_decimals,
    ) = price_feeds_data_consumer.getNativeTokenDataFeedLatestPriceAndDecimals()
    # Assert
    assert native_token_price > 0
    assert native_token_price_decimals > 0
