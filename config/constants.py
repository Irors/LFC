HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json',
    'origin': 'https://superbridge.app',
    'referer': 'https://superbridge.app/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

RPC_URL = "https://lisk.drpc.org"
CHAIN_ID_LISK = 1135

CHAINS_INFO = {
    1: "Ethereum",
    10: "Optimism",
    137: "Polygon",
    42161: "Arbitrum",
    324: "ZkSync",
    8453: "Base",
    534352: "Scroll",
}

TOKENS = {
    "ETH": "0x0000000000000000000000000000000000000000"
}

SUPERBRIDGE_API = "https://api.superbridge.app/api/v2/bridge/routes"
LAYERSWAP_NETWORKS = {
    "arbitrum": "ARBITRUM_MAINNET",
    "optimism": "OPTIMISM_MAINNET",
    "avalanche": "AVAX_MAINNET",
    "polygon": "POLYGON_MAINNET",
    "base": "BASE_MAINNET",
    "zksync": "ZKSYNCERA_MAINNET",
    "scroll": "SCROLL_MAINNET",
    "lisk": "LISK_MAINNET",
}

API_ENDPOINTS = {
    "RELAY": {
        "CHAINS": "https://api.relay.link/chains",
        "CONFIG": "https://api.relay.link/config/v2",
        "QUOTE": "https://api.relay.link/quote",
        "STATUS": "https://api.relay.link/intents/status/v2",
        "ORIGIN_CHAIN_ID": 1135
    }
}

CONTRACT_ADDRESSES = {
    "DMAIL": {'contract': "0x64812F1212f6276068A0726f4695a6637DA3E4F8", 'abi': '[{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"from","type":"address"},{"indexed":true,"internalType":"string","name":"to","type":"string"},{"indexed":true,"internalType":"string","name":"path","type":"string"}],"name":"Message","type":"event"},{"inputs":[{"internalType":"string","name":"to","type":"string"},{"internalType":"string","name":"path","type":"string"}],"name":"send_mail","outputs":[],"stateMutability":"nonpayable","type":"function"}]'},
    "SAFE": {'contract': "0x4e1dcf7ad4e460cfd30791ccc4f9c8a4f820ec67", "IMPLEMENTATION": "0x41675C099F32341bf84BFc5382aF534df5C7461a",         "ENCODED_PARAMS": "0xb63e800d00000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000001000000000000000000000000bd89a1ce4dde368ffab0ec35506eece0b1ffdc540000000000000000000000000000000000000000000000000000000000000140000000000000000000000000fd0732dc9e303f09fcef3a7388ad10a83459ec99000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000003a365f316f3b4f673b6ab5d64e512862be19d850000000000000000000000000000000000000000000000000000000000000024fe51f64300000000000000000000000029fcb43b46531bca003ddc8fcb67ffe91900c76200000000000000000000000000000000000000000000000000000000", "ABI": '[{"anonymous":false,"inputs":[{"indexed":true,"internalType":"contract SafeProxy","name":"proxy","type":"address"},{"indexed":false,"internalType":"address","name":"singleton","type":"address"}],"name":"ProxyCreation","type":"event"},{"inputs":[{"internalType":"address","name":"_singleton","type":"address"},{"internalType":"bytes","name":"initializer","type":"bytes"},{"internalType":"uint256","name":"saltNonce","type":"uint256"}],"name":"createChainSpecificProxyWithNonce","outputs":[{"internalType":"contract SafeProxy","name":"proxy","type":"address"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"_singleton","type":"address"},{"internalType":"bytes","name":"initializer","type":"bytes"},{"internalType":"uint256","name":"saltNonce","type":"uint256"},{"internalType":"contract IProxyCreationCallback","name":"callback","type":"address"}],"name":"createProxyWithCallback","outputs":[{"internalType":"contract SafeProxy","name":"proxy","type":"address"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"_singleton","type":"address"},{"internalType":"bytes","name":"initializer","type":"bytes"},{"internalType":"uint256","name":"saltNonce","type":"uint256"}],"name":"createProxyWithNonce","outputs":[{"internalType":"contract SafeProxy","name":"proxy","type":"address"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"getChainId","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"proxyCreationCode","outputs":[{"internalType":"bytes","name":"","type":"bytes"}],"stateMutability":"pure","type":"function"}]'},
    "IMPLEMENTATION": "0x41675C099F32341bf84BFc5382aF534df5C7461a",
    "JUMPER_SPENDER": "0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE"
}
