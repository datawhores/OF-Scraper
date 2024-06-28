def get_alt_params(ele):
    return {
        "Policy": ele.policy,
        "Key-Pair-Id": ele.keypair,
        "Signature": ele.signature,
    }
