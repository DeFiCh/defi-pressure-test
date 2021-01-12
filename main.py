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

# checkMinimumProfit returns False if minimum user's profit conditions are not met
def checkMinimumProfit(cfg, template):
    if template["estimatedReward"] < cfg.MinDfiReward:
        return "DeFi reward %s DFI < %s DFI" % (template["estimatedReward"], cfg.MinDfiReward)
    return None

# getFeeRate returns fee rate estimation according to user's rules
def getFeeRate(cfg, rpc):
    if cfg.Mode == "Fixed":
        return cfg.FixedRate
    return rpc.estimatesmartfee(cfg.Estimation.ConfTarget, cfg.Estimation.EstimateMode)["feerate"]

# isAnchorTx returns True if tx is anchor
def isAnchorTx(cfg, tx):
    for out in tx["vout"]:
        if "addresses" in out["scriptPubKey"] and cfg.AnchorsAddress in out["scriptPubKey"]["addresses"]:
            return True
    return False

# findCompetingAnchors returns list of txids of competing anchor txs
def findCompetingAnchors(cfg, rpc, myFeeRate, alreadyChecked, repeatingChecks):
    competingList = []
    txInfos = rpc.getrawmempool(True)
    for txid, txInfo in txInfos.items():
        if txid in alreadyChecked:
            continue
        if not "vsize" in txInfo:
            logging.critical("incompatible BTC RPC version (getrawmempool.vsize field not found)")
        if not "fees" in txInfo:
            logging.critical("incompatible BTC RPC version (getrawmempool.fees field not found)")
        alreadyChecked[txid] = True
        # check competing conditions. check it first because it's cheap
        feeRate = int((txInfo["fees"]["base"] * 100000000 * 1000) / Decimal(txInfo["vsize"]))/Decimal(100000000)
        age = time.time() - txInfo["time"]

        isCompetingFeeRate = feeRate * Decimal(cfg.Competing.FeeRateAdvantage) > myFeeRate
        isCompetingAge = age < cfg.Competing.TxTimeout

        if cfg.Competing.Mode == "OneOf" and (not isCompetingFeeRate or not isCompetingAge):
            continue # not competing
        if cfg.Competing.Mode == "AllOf" and (not isCompetingFeeRate and not isCompetingAge):
            continue # not competing

        # request full tx to check is it anchor tx
        try:
            tx = rpc.getrawtransaction(txid, True)
        except:
            continue # not found due to race condition

        if not isAnchorTx(cfg, tx):
            continue

        competingList.append(txid)

    # the check above took very long, so check new transactions which were received during the check (a few times).
    # the most time takes getrawtransaction, so each subsequent check will take much less time because only new transactions are checked
    if repeatingChecks != 0:
        competingList = competingList + findCompetingAnchors(cfg, rpc, myFeeRate, alreadyChecked, repeatingChecks - 1)

    return competingList

# anchor is the main routine to send an anchor transaction
def anchor(cfg, checkProfit, checkCompeting, createAnchor, sendAnchor):
    # Open RPC connections
    dfi = openRpc(cfg.DFI.RPC, None)
    btc = openRpc(cfg.BTC.RPC, cfg.BTC.Wallet.WalletName)

    # Check RPC connection
    testRpc(dfi, "DeFi")
    testRpc(btc, "Bitcoin")

    # Get BTC feerate
    feeRate = getFeeRate(cfg.BTC.Wallet.FeeRate, btc)

    if checkCompeting:
        log.info("checking competing anchors in BTC mempool")
        competingTxs = findCompetingAnchors(cfg.DFI.Anchoring, btc, feeRate, {}, 3)
        if competingTxs:
            logging.critical("competing anchors present in mempool: %s" % competingTxs)
        log.success("ok\n")
    else:
        log.warning("skip checking competing anchors in BTC mempool\n")

    log.info("requesting anchor template from DeFi RPC")
    template = dfi.spv_createanchortemplate(cfg.DFI.Anchoring.RewardAddress)
    log.info("* DeFi block      : %s" % template["defiHash"])
    log.info("* potential reward: %s DFI" % template["estimatedReward"])
    log.success("ok\n")

    if checkProfit:
        log.info("checking minimum profit conditions")
        err = checkMinimumProfit(cfg.DFI.Anchoring.Profit, template)
        if err:
            logging.critical("Minimum profit conditions not met: %s" % err)
        log.success("ok\n")
    else:
        log.warning("skip checking minimum profit conditions\n")

    if not createAnchor:
        log.warning("skip creation of anchor transaction\n")
        return

    log.info("creation of anchor transaction")
    try:
        outsLen = len(btc.decoderawtransaction(template["txHex"])["vout"])
        fundedTx = btc.fundrawtransaction(template["txHex"], {"feeRate": feeRate, "changePosition": outsLen})
    except Exception as e:
        logging.critical("failed to fund transaction: %s" % e)
    try:
        signedTx = btc.signrawtransactionwithwallet(fundedTx["hex"])
        if signedTx["complete"] == False:
            raise Exception("not all addresses are known")
    except Exception as e:
        logging.critical("failed to sign transaction: %s" % e)
    log.success("ok\n")

    if not sendAnchor:
        log.warning("skip sending anchor transaction")
        return

    # Send anchor tx
    log.info("sending anchor transaction")
    txid = btc.sendrawtransaction(signedTx["hex"])
    log.info("* BTC anchor transaction: %s" % txid)
    log.info("* DeFi block            : %s" % template["defiHash"])
    log.info("* potential reward      : %s DFI" % template["estimatedReward"])
    log.success("ok\n")

def testTransferToken(cfg, dfiRpc):
    if cfg.TXN.TYPE.UTXO:
        reply = dfiRpc.sendtoaddress(cfg.TXN.ADDR.toAddr, 0.1)
        logging.info("sendtoaddress repy: " + reply)

def testUtxosToAccounts(cfg, dfiRpc):
    if cfg.TXN.TYPE.UTXO_TO_ACC:
        logging.info('Start to test utxostoaccount')
        input = dict()
        input[cfg.TXN.ADDR.fromAddr] = '0.1@DFI'
        reply = dfiRpc.utxostoaccount(input)
        logging.info('utxostoaccount reply: ' + reply)

def testAccountToUtxos(cfg, dfiRpc):
    if cfg.TXN.TYPE.ACC_TO_UTXO:
        logging.info('Start to test accounttoutxos')
        toObj = dict()
        toObj[cfg.TXN.ADDR.toAddr] = '0.1@DFI'
        reply = dfiRpc.accounttoutxos(cfg.TXN.ADDR.fromAddr, toObj)
        logging.info('accounttoutxos reply: ' + reply)

def testAccountToAccount(cfg, dfiRpc):
    if cfg.TXN.TYPE.ACC_TO_ACC:
        logging.info('Start to test accounttoaccount')
        toObj = dict()
        toObj[cfg.TXN.ADDR.toAddr] = '0.1@MyToken3#131'
        reply = dfiRpc.accounttoaccount(cfg.TXN.ADDR.fromAddr, toObj)
        logging.info('accounttoaccount reply: ' + reply)

def testPoolSwap(cfg, dfiRpc):
    if cfg.TXN.TYPE.POOL_SWAP:
        logging.info('Start to test poolswap')
        metaData = dict()
        metaData['from'] = cfg.TXN.ADDR.fromAddr
        metaData['tokenFrom'] = cfg.TXN.ADDR.tokenFrom
        metaData['amountFrom'] = 10
        metaData['to'] = cfg.TXN.ADDR.toAddr
        metaData['tokenTo'] = cfg.TXN.ADDR.tokenTo
        metaData['maxPrice'] = 100
        reply = dfiRpc.poolswap(metaData)
        logging.info('poolswap reply: ' + reply)


def testDefiChain(cfg):
    # Open RPC connections
    dfiRpc = openRpc(cfg.DFI.RPC, None)

    # Check RPC connection
    testRpc(dfiRpc, "DeFi")
    testTransferToken(cfg, dfiRpc)
    testUtxosToAccounts(cfg, dfiRpc)
    testAccountToUtxos(cfg, dfiRpc)
    testAccountToAccount(cfg, dfiRpc)
    testPoolSwap(cfg, dfiRpc)


if __name__ == '__main__':
    # Load config
    parser = argparse.ArgumentParser(description='A simple script to submit DeFi anchors on BTC blockchain.')
    parser.add_argument('--config', metavar='config.toml', dest='config', type=str, required=True,
                        help='config file in TOML format')
    parser.add_argument('--checkprofit', dest='checkprofit', type=str, required=False, default="yes", choices=["yes", "no"],
                        help='check minimum profit conditions (default: yes)')
    parser.add_argument('--checkcompeting', dest='checkcompeting', type=str, required=False, default="yes", choices=["yes", "no"],
                        help='check competing anchor transactions in mempool (default: yes)')
    parser.add_argument('--createanchor', dest='createanchor', type=str, required=False, default="yes", choices=["yes", "no"],
                        help='create the anchor transaction (default: yes)')
    parser.add_argument('--sendanchor', dest='sendanchor', type=str, required=False, default="yes", choices=["yes", "no"],
                        help='send the anchor transaction (default: yes)')
    parser.add_argument('--repeat', metavar='period', dest='repeat', type=float, required=False, default=0,
                        help='run the script within infinite loop every T seconds. if 0, then run only once (default: 0)')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Read config
    cfg = config.mustLoad(args.config)

    # Execute main routine
    while True:
        exitCode = 1
        try:
            testDefiChain(cfg)
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
