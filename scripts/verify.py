import json

from pathlib import Path
from brownie import (
    AutomatedVaultERC4626,
    AutomatedVaultsFactory,
)

FACTORY_ADDRESS = "" # TODO: ADD DEPLOYED FACTORY ADDRESS
PATH_TO_DATA = str(Path("./scripts/data/script_data.json").resolve())


def verify_vaults():
    with open(PATH_TO_DATA) as file:
        data = json.load(file)
        last_verified_vault = data["last_verified_vault"]
        factory_contract = AutomatedVaultsFactory.at(FACTORY_ADDRESS)
        vault_length = factory_contract.allVaultsLength()

        if vault_length == 0 or vault_length - last_verified_vault == 1:  # All vaults have been verified or no vault exists
            return
        
        vaults_failed_to_verify = []
        start_after = last_verified_vault + 1
        vaults = factory_contract.getBatchVault(vault_length, start_after)

        for i, vault in enumerate(vaults, start=start_after):
            vault_contract = AutomatedVaultERC4626.at(vault)
            published = AutomatedVaultERC4626.publish_source(vault_contract)
            if not published:
                vaults_failed_to_verify.append((i, vault))

        # If all contracts are sucessfully verified the last verified vault is length - 1 else is the place where the first vault failed.
        data["last_verified_vault"] = vaults_failed_to_verify[0][0] - 1 if vaults_failed_to_verify else vault_length-1
        data = json.dump(data)
        file.write(data)
        
