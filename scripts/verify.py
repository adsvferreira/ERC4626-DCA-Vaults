import json

from pathlib import Path
from helpers import CONSOLE_SEPARATOR
from brownie import (
    config,
    network,
    AutomatedVaultERC4626,
    AutomatedVaultsFactory,
)

PATH_TO_DATA = str(Path("./scripts/data/script_data.json").resolve())
FACTORY_ADDRESS = config["networks"][network.show_active()]["vaults_factory_address"]


def main():
    # NETWORK
    print(CONSOLE_SEPARATOR)
    print("CURRENT NETWORK: ", network.show_active())
    print(CONSOLE_SEPARATOR)

    with open(PATH_TO_DATA) as file:
        data = json.load(file)
        last_verified_vault = data["last_verified_vault"]
        factory_contract = AutomatedVaultsFactory.at(FACTORY_ADDRESS)
        vault_length = factory_contract.allVaultsLength()

        if vault_length == 0:
            print('No vaults have been deployed!')
            return
        if vault_length - last_verified_vault == 1:
            print("All vaults have been verified.")
            return
        
        vaults_verified = []
        vaults_failed_to_verify = []
        start_after = last_verified_vault + 1
        vaults = factory_contract.getBatchVault(vault_length, start_after)

        for i, vault in enumerate(vaults, start=start_after):
            vault_contract = AutomatedVaultERC4626.at(vault)
            published = AutomatedVaultERC4626.publish_source(vault_contract)
            if not published:
                vaults_failed_to_verify.append((i, vault))
            else:
                vaults_verified.append((i, vault))

        # If all contracts are sucessfully verified the last verified vault is length - 1 else is the first failed vault index
        data["last_verified_vault"] = vaults_failed_to_verify[0][0] - 1 if vaults_failed_to_verify else vault_length-1
        data = json.dump(data)
        file.write(data)
        print(f"Execution completed!\n Validated Vaults: {[vault for _, vault in vaults_verified]}.\n Vaults that failed during validation: {[vault for _, vault in vaults_failed_to_verify]}")
        
