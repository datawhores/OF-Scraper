def get_alt_params(ele):
    return {
        "Policy": ele.policy,
        "Key-Pair-Id": ele.keypair,
        "Signature": ele.signature,
    }


def get_alt_params_hls(ele):
    return {
        "Policy": ele.hls_policy,
        "Key-Pair-Id": ele.hls_keypair,
        "Signature": ele.hls_signature,
    }
