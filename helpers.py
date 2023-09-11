from brownie import accounts, config, network

def get_account_from_pk(index:int)->object:
    return accounts.add(config["wallets"][f"from_key_{index}"])
