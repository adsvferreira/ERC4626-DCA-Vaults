from typing import List
from dataclasses import dataclass


@dataclass
class StrategyVault:
    address: str
    creator: str
    deposit_token_address: str
    token_addresses_to_buy: List[str]
    depositor_addresses: List[str]
    buy_frequency_timestamp: int
    last_update_timestamp: int
