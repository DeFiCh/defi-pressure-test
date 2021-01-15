#!/usr/bin/env python3

from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from decimal import *
from datetime import datetime
import config
import sys
import logging
import time
import argparse

# openRpc connection
def openRpc(cfg, walletName):
    url = "http://%s:%s@%s:%s/"%(cfg.User, cfg.Password, cfg.Hostname, cfg.Port)
    if walletName != None:
        url += "wallet/%s" % walletName

    return AuthServiceProxy(url)

# testRpc exits if RPC fails
def testRpc(rpc, name):
    try:
        reply = rpc.getbestblockhash()
        print('getbestblockhash result '+ reply)
    except ConnectionRefusedError as e:
        logging.critical("%s RPC connection refused: %s" % (name, e))
    except JSONRPCException as e:
        logging.critical("%s RPC error: %s" % (name, e))

def testMintToken(cfg, dfiRpc):
    if cfg.TXN.TYPE.MINT_TOKEN:
        reply = dfiRpc.minttokens('100@' + cfg.TXN.ADDR.tokenFrom)
        logging.info(cfg.TXN.ADDR.tokenFrom + " minttokens repy: " + reply)

        reply = dfiRpc.minttokens('100@' + cfg.TXN.ADDR.tokenTo)
        logging.info(cfg.TXN.ADDR.tokenTo + " minttokens repy: " + reply)

def testTransferToken(cfg, dfiRpc):
    if cfg.TXN.TYPE.UTXO:
        reply = dfiRpc.sendtoaddress(cfg.TXN.ADDR.addrTo, 0.1)
        logging.info("sendtoaddress repy: " + reply)

def testUtxosToAccounts(cfg, dfiRpc):
    if cfg.TXN.TYPE.UTXO_TO_ACC:
        logging.info('Start to test utxostoaccount')
        input = dict()
        input[cfg.TXN.ADDR.addrFrom] = '0.1@DFI'
        reply = dfiRpc.utxostoaccount(input)
        logging.info('utxostoaccount reply: ' + reply)

def testAccountToUtxos(cfg, dfiRpc):
    if cfg.TXN.TYPE.ACC_TO_UTXO:
        logging.info('Start to test accounttoutxos')
        toObj = dict()
        toObj[cfg.TXN.ADDR.addrTo] = '0.1@DFI'
        reply = dfiRpc.accounttoutxos(cfg.TXN.ADDR.addrFrom, toObj)
        logging.info('accounttoutxos reply: ' + reply)

def testAccountToAccount(cfg, dfiRpc):
    if cfg.TXN.TYPE.ACC_TO_ACC:
        logging.info('Start to test accounttoaccount')
        toObj = dict()
        toObj[cfg.TXN.ADDR.addrTo] = '0.1@' + cfg.TXN.ADDR.tokenTo
        reply = dfiRpc.accounttoaccount(cfg.TXN.ADDR.addrFrom, toObj)
        logging.info('accounttoaccount reply: ' + reply)

def testAddLiquidity(cfg, dfiRpc):
    if cfg.TXN.TYPE.ADD_LIQUIDITY:
        logging.info('Start to test addpoolliquidity')
        metaData = dict()
        tokens = list()
        tokens.append("10@" + cfg.TXN.ADDR.tokenFrom)
        tokens.append("10@" + cfg.TXN.ADDR.tokenTo)
        metaData[cfg.TXN.ADDR.addrFrom] = tokens
        reply = dfiRpc.addpoolliquidity(metaData, cfg.TXN.ADDR.addrFrom)
        logging.info('addpoolliquidity reply: ' + reply)

def testPoolSwap(cfg, dfiRpc, testTime):
    if cfg.TXN.TYPE.POOL_SWAP:
        logging.info('Start to test poolswap')
        metaData = dict()
        if testTime % 2 == 1:
            metaData['from'] = cfg.TXN.ADDR.addrFrom
            metaData['tokenFrom'] = cfg.TXN.ADDR.tokenFrom
            metaData['amountFrom'] = 1
            metaData['to'] = cfg.TXN.ADDR.addrTo
            metaData['tokenTo'] = cfg.TXN.ADDR.tokenTo
        else:
            metaData['from'] = cfg.TXN.ADDR.addrTo
            metaData['tokenFrom'] = cfg.TXN.ADDR.tokenTo
            metaData['amountFrom'] = 1
            metaData['to'] = cfg.TXN.ADDR.addrFrom
            metaData['tokenTo'] = cfg.TXN.ADDR.tokenFrom
        metaData['maxPrice'] = 100
        reply = dfiRpc.poolswap(metaData)
        logging.info('poolswap reply: ' + reply)

def genBlock(cfg, dfiRpc):
    if cfg.DFI.RPC.REGTEST:
        print(cfg.TXN.ADDR.addrFrom)
        reply = dfiRpc.generatetoaddress(2, cfg.TXN.ADDR.addrFrom)
        logging.info('generatetoaddress reply: ' + str(reply))

def testDefiChain(cfg, testTime):
    # Open RPC connections
    dfiRpc = openRpc(cfg.DFI.RPC, None)

    # Check RPC connection
    testRpc(dfiRpc, "DeFi")
    testMintToken(cfg, dfiRpc)
    testTransferToken(cfg, dfiRpc)
    testUtxosToAccounts(cfg, dfiRpc)
    testAccountToUtxos(cfg, dfiRpc)
    testAccountToAccount(cfg, dfiRpc)
    testAddLiquidity(cfg, dfiRpc)
    testPoolSwap(cfg, dfiRpc, testTime)
    genBlock(cfg, dfiRpc)

if __name__ == '__main__':
    # Load config
    parser = argparse.ArgumentParser(description='A simple script to submit DeFi anchors on BTC blockchain.')
    parser.add_argument('--config', metavar='config.toml', dest='config', type=str, required=True,
                        help='config file in TOML format')
    parser.add_argument('--repeat', metavar='period', dest='repeat', type=float, required=False, default=0,
                        help='run the script within infinite loop every T seconds. if 0, then run only once (default: 0)')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Read config
    cfg = config.mustLoad(args.config)

    testTime = 0
    # Execute main routine
    while True:
        testTime = testTime + 1
        exitCode = 1
        try:
            testDefiChain(cfg, testTime)
            exitCode = 0
        except ConnectionRefusedError as e:
            logging.error("RPC connection refused: %s" % e)
        except JSONRPCException as e:
            logging.error("RPC error: %s" % e)
        except Exception as e:
            logging.error("Error: %s" % e)

        if args.repeat == 0:
            sys.exit(exitCode)
        time.sleep(args.repeat)
        logging.info("\n%s repeating the routine" % datetime.now())
        logging.info("================================================\n")
