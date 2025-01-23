import segwit_addr as sa
import hashlib


def ckbhash():
    return hashlib.blake2b(digest_size=32, person=b'ckb-default-hash')


# ref: https://github.com/nervosnetwork/rfcs/blob/master/rfcs/0021-ckb-address-format/0021-ckb-address-format.md
FORMAT_TYPE_FULL = 0x00
FORMAT_TYPE_SHORT = 0x01
FORMAT_TYPE_FULL_DATA = 0x02
FORMAT_TYPE_FULL_TYPE = 0x04

CODE_INDEX_SECP256K1_SINGLE = 0x00
CODE_INDEX_SECP256K1_MULTI = 0x01
CODE_INDEX_ACP = 0x02

BECH32_CONST = 1
BECH32M_CONST = 0x2bc830a3

# ref: https://github.com/nervosnetwork/rfcs/blob/master/rfcs/0024-ckb-system-script-list/0024-ckb-system-script-list.md
SCRIPT_CONST_MAINNET = {
    CODE_INDEX_SECP256K1_SINGLE: {
        "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
        "hash_type": "type",
        "tx_hash": "0x71a7ba8fc96349fea0ed3a5c47992e3b4084b031a42264a018e0072e8172e46c",
        "index": "0",
        "dep_type": "dep_group"
    },
    CODE_INDEX_SECP256K1_MULTI: {
        "code_hash": "0x5c5069eb0857efc65e1bca0c07df34c31663b3622fd3876c876320fc9634e2a8",
        "hash_type": "type",
        "tx_hash": "0x71a7ba8fc96349fea0ed3a5c47992e3b4084b031a42264a018e0072e8172e46c",
        "index": "1",
        "dep_type": "dep_group"
    },
    CODE_INDEX_ACP: {
        "code_hash": "0xd369597ff47f29fbc0d47d2e3775370d1250b85140c670e4718af712983a2354",
        "hash_type": "type",
        "tx_hash": "0x4153a2014952d7cac45f285ce9a7c5c0c0e1b21f2d378b82ac1433cb11c25c4d",
        "index": "0",
        "dep_type": "dep_group"
    }
}

SCRIPT_CONST_TESTNET = {
    CODE_INDEX_SECP256K1_SINGLE: {
        "code_hash": "0x9bd7e06f3ecf4be0f2fcd2188b23f1b9fcc88e5d4b65a8637b17723bbda3cce8",
        "hash_type": "type",
        "tx_hash": "0xf8de3bb47d055cdf460d93a2a6e1b05f7432f9777c8c474abf4eec1d4aee5d37",
        "index": "0",
        "dep_type": "dep_group"
    },
    CODE_INDEX_SECP256K1_MULTI: {
        "code_hash": "0x5c5069eb0857efc65e1bca0c07df34c31663b3622fd3876c876320fc9634e2a8",
        "hash_type": "type",
        "tx_hash": "0xf8de3bb47d055cdf460d93a2a6e1b05f7432f9777c8c474abf4eec1d4aee5d37",
        "index": "1",
        "dep_type": "dep_group"
    },
    CODE_INDEX_ACP: {
        "code_hash": "0x3419a1c09eb2567f6552ee7a8ecffd64155cffe0f1796e6e61ec088d740c1356",
        "hash_type": "type",
        "tx_hash": "0xec26b0f85ed839ece5f11c4c4e837ec359f5adc4420410f6453b1f6b60fb96a6",
        "index": "0",
        "dep_type": "dep_group"
    }
}


def decodeAddress(addr, network="mainnet"):
    hrp = {"mainnet": "ckb", "testnet": "ckt"}[network]
    hrpgot, data, spec = sa.bech32_decode(addr)
    if hrpgot != hrp or data == None:
        return False
    decoded = sa.convertbits(data, 5, 8, False)
    if decoded == None:
        return False
    payload = bytes(decoded)
    format_type = payload[0]
    if format_type == FORMAT_TYPE_FULL:
        ptr = 1
        code_hash = "0x" + payload[ptr: ptr + 32].hex()
        ptr += 32
        hash_type = payload[ptr: ptr + 1].hex()
        ptr += 1
        args = "0x" + payload[ptr:].hex()
        return ("full", code_hash, hash_type, args)
    elif format_type == FORMAT_TYPE_SHORT:
        code_index = payload[1]
        pk = "0x" + payload[2:].hex()
        return ("short", code_index, pk)
    elif format_type == FORMAT_TYPE_FULL_DATA or format_type == FORMAT_TYPE_FULL_TYPE:
        full_type = {FORMAT_TYPE_FULL_DATA: "Data", FORMAT_TYPE_FULL_TYPE: "Type"}[format_type]
        ptr = 1
        code_hash = payload[ptr: ptr + 32].hex()
        ptr += 32
        args = payload[ptr:].hex()
        return ("deprecated full", full_type, code_hash, args)


if __name__ == "__main__":
    addr = "ckt1qzda0cr08m85hc8jlnfp3zer7xulejywt49kt2rr0vthywaa50xwsqfy4w0gqjsm0ulnq0l4ft6hu6spztrj72sjtcnx4"
    result = decodeAddress(addr, "testnet")
    if result:
        print(f"Address Type: {result[0]}")
        print(f"Code Hash: {result[1]}")
        print(f"Hash Type: {result[2]}")  # 只有全地址类型才有 hash_type
        print(f"Args: {result[3]}")  # 只有全地址类型才有 args
    else:
        print("Invalid or unsupported address format.")
