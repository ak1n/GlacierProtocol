#!/usr/bin/env python

################################################################################################
#
# GlacierScript:  Part of the Glacier Protocol (http://glacierprotocol.org)
#
# GlacierScript is designed specifically for use in the context of executing the broader Glacier
# Protocol, a step-by-step procedure for high-security cold storage of Bitcoin.  It is not
# intended to be used as standalone software.
#
# GlacierScript primarily replaces tasks that users would otherwise be doing manually, such as
# typing things on the command line, copying-and-pasting strings, and hand-editing JSON.  It
# mostly consists of print statements, user input, string & JSON manipulation, and command-line
# wrappers around Bitcoin Core and other applications (e.g. those involved in reading and writing
# QR codes.)
#
# GlacierScript avoids cryptographic and other security-sensitive operations as much as possible.
#
# GlacierScript depends on the following command-line applications:
# - Bitcoin Core (http://bitcoincore.org)
# - qrencode (QR code writer: http://packages.ubuntu.com/xenial/qrencode)
# - zbarimg (QR code reader: http://packages.ubuntu.com/xenial/zbar-tools)
#
################################################################################################

# standard Python libraries
import time
import argparse
import os
import sys
import hashlib
from hashlib import sha256, md5
import random
import subprocess
import json
from decimal import Decimal

# Taken from Gavin Andresen's "bitcointools" python library (exact link in source file)
from base58 import b58encode

SATOSHI_PLACES = Decimal("0.00000001")
SATOSHI_MBTC_PLACES = Decimal("0.00001")
SATOSHI_MICROBTC_PLACES = Decimal("0.01")

verbose_mode = 0
re_sign_mode = 0
single_safety_confirm_mode = 0

################################################################################################
#
# Minor helper functions
#
################################################################################################

def hash_sha256(s):
    """A thin wrapper around the hashlib SHA256 library to provide a more functional interface"""
    m = sha256()
    m.update(s)
    return m.hexdigest()


def hash_md5(s):
    """A thin wrapper around the hashlib md5 library to provide a more functional interface"""
    m = md5()
    m.update(s)
    return m.hexdigest()


def satoshi_to_btc(satoshi):
    """
    Converts a value in satoshi to a value in BTC
    outputs => Decimal

    satoshi: <int>
    """
    value = Decimal(satoshi) / Decimal(100000000)
    return value.quantize(SATOSHI_PLACES)


def btc_to_satoshi(btc):
    """
    Converts a value in BTC to satoshi
    outputs => <int>

    btc: <Decimal> or <Float>
    """
    value = btc * 100000000
    return int(value)

def verbose(content):
    if verbose_mode: print content

################################################################################################
#
# Read & validate random data from the user
#
################################################################################################

def validate_rng_seed(seed, min_length):
    """
    Validates random hexadecimal seed
    returns => <boolean>

    seed: <string> hex string to be validated
    min_length: <int> number of characters required.  > 0
    """

    if len(seed) < min_length:
        print "Error: Computer entropy must be at least {0} characters long".format(min_length)
        return False

    if len(seed) % 2 != 0:
        print "Error: Computer entropy must contain an even number of characters."
        return False

    try:
        int(seed, 16)
    except ValueError:
        print "Error: Illegal character. Computer entropy must be composed of hexadecimal characters only (0-9, a-f)."
        return False

    return True


def read_rng_seed_interactive(min_length):
    """
    Reads random seed (of at least min_length hexadecimal characters) from standard input
    returns => string

    min_length: <int> minimum number of bytes in the seed.
    """

    char_length = min_length * 2

    def ask_for_rng_seed(length):
        print "Enter at least {0} characters of computer entropy. Spaces are OK, and will be ignored:".format(length)

    ask_for_rng_seed(char_length)
    seed = raw_input()
    seed = unchunk(seed)

    while not validate_rng_seed(seed, char_length):
        ask_for_rng_seed(char_length)
        seed = raw_input()
        seed = unchunk(seed)

    return seed


def validate_dice_seed(dice, min_length):
    """
    Validates dice data (i.e. ensures all digits are between 1 and 6).
    returns => <boolean>

    dice: <string> representing list of dice rolls (e.g. "5261435236...")
    """

    if len(dice) < min_length:
        print "Error: You must provide at least {0} dice rolls".format(min_length)
        return False

    for die in dice:
        try:
            i = int(die)
            if i < 1 or i > 6:
                print "Error: Dice rolls must be between 1 and 6."
                return False
        except ValueError:
            print "Error: Dice rolls must be numbers between 1 and 6"
            return False

    return True


def read_dice_seed_interactive(min_length):
    """
    Reads min_length dice rolls from standard input, as a string of consecutive integers
    Returns a string representing the dice rolls
    returns => <string>

    min_length: <int> number of dice rolls required.  > 0.
    """

    def ask_for_dice_seed(x):
        print "Enter {0} dice rolls (example: 62543 16325 21341...) Spaces are OK, and will be ignored:".format(x)

    ask_for_dice_seed(min_length)
    dice = raw_input()
    dice = unchunk(dice)

    while not validate_dice_seed(dice, min_length):
        ask_for_dice_seed(min_length)
        dice = raw_input()
        dice = unchunk(dice)

    return dice


################################################################################################
#
# private key generation
#
################################################################################################

def xor_hex_strings(str1, str2):
    """
    Return xor of two hex strings.
    An XOR of two pieces of data will be as random as the input with the most randomness.
    We can thus combine two entropy sources in this way as a safeguard against one source being
    compromised in some way.
    For details, see http://crypto.stackexchange.com/a/17660

    returns => <string> in hex format
    """
    if len(str1) != len(str2):
        raise Exception("tried to xor strings of unequal length")
    str1_dec = int(str1, 16)
    str2_dec = int(str2, 16)

    xored = str1_dec ^ str2_dec

    return "{:0{}x}".format(xored, max(len(str1), len(str2)))


def hex_private_key_to_WIF_private_key(hex_key):
    """
    Converts a raw 256-bit hex private key to WIF format
    returns => <string> in hex format
    """

    hex_key_with_prefix = wif_prefix + hex_key + "01"

    h1 = hash_sha256(hex_key_with_prefix.decode("hex"))
    h2 = hash_sha256(h1.decode("hex"))
    checksum = h2[0:8]

    wif_key_before_base58Check = hex_key_with_prefix + checksum
    wif_key = b58encode(wif_key_before_base58Check.decode("hex"))

    return wif_key


################################################################################################
#
# Bitcoin helper functions
#
################################################################################################

def ensure_bitcoind_running():
    """
    Start bitcoind (if it's not already running) and ensure it's functioning properly
    """
    devnull = open("/dev/null")

    # start bitcoind.  If another bitcoind process is already running, this will just print an error
    # message (to /dev/null) and exit.
    #
    # -connect=0.0.0.0 because we're doing local operations only (and have no network connection anyway)
    #
    # The only way to make our signrawtransaction compatible with both 0.16 and 0.17 is using this -deprecatedrpc=signrawtransaction..
    # Once Bitcoin Core v0.17 is published on the Ubuntu PPA we should:
    # 1. Convert signrawtransaction to signrawtransactionwithkeys (note, argument order changes)
    # 2. Remove this -deprecatedrpc=signrawtransaction
    # 3. Change getaddressesbyaccount to getaddressesbylabel
    # 4. Remove this -deprecatedrpc=accounts
    bitcoin_cli_call("","-daemon -connect=0.0.0.0 -deprecatedrpc=signrawtransaction -deprecatedrpc=accounts", use_bitcoind=1, call_type=1, stdout=devnull, stderr=devnull)

    # verify bitcoind started up and is functioning correctly
    times = 0
    while times <= 20:
        times += 1
        if bitcoin_cli_call("getnetworkinfo", "", call_type=1, stdout=devnull, stderr=devnull) == 0:
            return
        time.sleep(0.5)

    raise Exception("Timeout while starting bitcoin server")

def require_minimum_bitcoind_version(min_version):
    """
    Fail if the bitcoind version in use is older than required
    <min_version> - required minimum version in format of getnetworkinfo, i.e. 150100 for v0.15.1
    """
    networkinfo_str = bitcoin_cli_call("getnetworkinfo","")
    networkinfo = json.loads(networkinfo_str)

    if int(networkinfo["version"]) < min_version:
        print "ERROR: Your bitcoind version is too old. You have {}, I need {} or newer. Exiting...".format(networkinfo["version"], min_version)
        sys.exit()

def get_address_for_wif_privkey(privkey):
    """A method for retrieving the address associated with a private key from bitcoin core
       <privkey> - a bitcoin private key in WIF format"""

    # Bitcoin Core doesn't have an RPC for "get the addresses associated w/this private key"
    # just "get the addresses associated with this account"
    # where "account" corresponds to an arbitrary tag we can associate with each private key
    # so, we'll generate a unique "account number" to put this private key into.
    #
    # we're running on a fresh bitcoind installation in the Glacier Protocol, so there's no
    # meaningful risk here of colliding with previously-existing account numbers.
    account_number = random.randint(0, 2**128)

    ensure_bitcoind_running()
    bitcoin_cli_call("importprivkey", "{0} {1}".format(privkey, account_number), call_type=1)
    addresses = bitcoin_cli_call("getaddressesbyaccount", account_number)

    # extract address from JSON output
    addresses_json = json.loads(addresses)
    return addresses_json[0]


def addmultisigaddress(m, addresses_or_pubkeys, address_type='p2sh-segwit'):
    """
    Call `bitcoin-cli addmultisigaddress`
    returns => JSON response from bitcoin-cli

    m: <int> number of multisig keys required for withdrawal
    addresses_or_pubkeys: List<string> either addresses or hex pubkeys for each of the N keys
    """

    require_minimum_bitcoind_version(160000) # addmultisigaddress API changed in v0.16.0
    address_string = json.dumps(addresses_or_pubkeys)
    argstring = "{0} '{1}' '' '{2}'".format(m, address_string, address_type)
    return json.loads(bitcoin_cli_call("addmultisigaddress", argstring))

def get_utxos(tx, address):
    """
    Given a transaction, find all the outputs that were sent to an address
    returns => List<Dictionary> list of UTXOs in bitcoin core format

    tx - <Dictionary> in bitcoind core format
    address - <string>
    """
    utxos = []

    for output in tx["vout"]:
        if "addresses" not in output["scriptPubKey"]:
            # In Bitcoin Core versions older than v0.16, native segwit outputs have no address decoded
            continue
        out_addresses = output["scriptPubKey"]["addresses"]
        amount_btc = output["value"]
        if address in out_addresses:
            utxos.append(output)

    return utxos

def get_raw_tx_interactive(unique_init_prompt):
    # handle inputting of raw tx hex. display initial prompt specific to the input
    # will be called from fns:
    #   parse_part_signed_tx (for re-sign of partially-signed tx)
    #   withdraw_interactive (for input tx; pending testing revision to not break make)
    print "\n{0}".format(unique_init_prompt)
    print "\n  Please paste the raw transaction (hexadecimal format) with unspent outputs at the source address"
    print "  OR"
    print "  input a filename located in the current directory which contains the raw transaction data"
    print "  (If the transaction data is over ~4000 characters long, you _must_ use a file.):"

    raw_tx = raw_input()
    if os.path.isfile(raw_tx):
        raw_tx = open(raw_tx).read().strip()
    return raw_tx

def parse_part_signed_tx(source_address):
    # parses partially-signed transaction hex for tx data (to later re-sign)
    # inputs: source/cold address (arg), part-signed tx hex (manual in fn, passed as output)
    # outputs parsed: redeem_script, dest_address, change_amount, withdrawal_amount, num_tx
    part_signed_tx_hex = get_raw_tx_interactive("For the partially-signed transaction")

    part_signed_tx = json.loads(bitcoin_cli_call("decoderawtransaction",part_signed_tx_hex))
    redeem_script=part_signed_tx["vin"][0]["txinwitness"][-1]
    num_tx = len(part_signed_tx["vin"])

    # parse change amount & destination address from partly-signed data
    if len(part_signed_tx["vout"]) is 1:
        verbose("only 1 transaction output indicates entire balance being withdrawn (change amount = 0)")
        #thus destination address data in vout[0]
        change_amount = Decimal(0)
        withdrawal_amount = Decimal(part_signed_tx["vout"][0]["value"]).quantize(SATOSHI_PLACES)
        dest_address = part_signed_tx["vout"][0]["scriptPubKey"]["addresses"][0]
    else:
        verbose("multiple outputs indicates change to be delivered back to cold storage address")
        # ascertain where destination and change addresses are in vout array
        cold_storage_vout_index = -1
        destination_vout_index = -1
        i = 0
        for output in part_signed_tx["vout"]:
            for address in output["scriptPubKey"]["addresses"]:
                if address == source_address:
                    cold_storage_vout_index = i
                    break
            i += 1

        if cold_storage_vout_index is -1:
            print "could not find cold storage source address in partially signed transaction hex (more than 1 output without cold address found in these for change!)! exiting..."
            sys.exit()
        if cold_storage_vout_index == 0:
            destination_vout_index = 1
        else:
            destination_vout_index = 0
        dest_address = part_signed_tx["vout"][destination_vout_index]["scriptPubKey"]["addresses"][0]

        # now parse out amounts knowing array positions of source/destination vouts
        change_amount = Decimal(part_signed_tx["vout"][cold_storage_vout_index]["value"]).quantize(SATOSHI_PLACES)
        withdrawal_amount = Decimal(part_signed_tx["vout"][destination_vout_index]["value"]).quantize(SATOSHI_PLACES)

        print"\nfollowing variables parsed from partially signed hex input & storage address:"
        print "\n    cold storage / source_address: {0} (for reference from manual input)".format(source_address)
    print "\n    redemption script: {0}".format(redeem_script)
    print "\n    destination address: {0}".format(dest_address)
    print "\n    number of input transactions: {0}".format(num_tx)
    print "\n    change amount: {0}".format(change_amount)
    print "\n    withdrawal amount: {0}".format(withdrawal_amount)

    print "\n\nplease confirm whether above data is correct before proceeding to input additional data for transaction re-sign"
    confirm = yes_no_interactive()
    if not confirm:
        print "auto parsed data from transaction incorrect so aborting"
        sys.exit()
    return part_signed_tx_hex, redeem_script, dest_address, change_amount, withdrawal_amount, num_tx


def check_fee_to_input_amt(fee, input_amount):
    # check that a fee set for a transaction does not exceed available input transactions
    # will be called from withdrawal interactive in both full & sequential sign modes (but at different points)
    if fee > input_amount:
        print "ERROR: Your fee is greater than the sum of your unspent transactions.  Try using larger unspent transactions. Exiting..."
        sys.exit()

def zero_less_than_satoshi(btc):
    # less than a satoshi due to weird floating point imprecision
    # this originally applied only to change amount, but display problems can also happen with 0 Decimals
    #   if attempt to display 0 with Decimal to satoshi will get 0E-8 (noted on consolidating btc display)
    if btc < 1e-8:
        btc = 0
    return btc

def btc_display(btc):
    # streamline display of btc including mbtc if < 1 btc (& in comments microbtc if < 1 mbtc)
    #   reduce user errors (e.g. w counting decimals in fee checking)
    # note: calls SHOULD initially break existing testing as changing display output
    # 8 call points will include:
    #   get_fee_interactive: multiple calls ("bitcoins")
    #   withdraw_interactive: multiple calls ("BTC", "bitcoins")
    btc = zero_less_than_satoshi(Decimal(btc).quantize(SATOSHI_PLACES))
    
    expanded_display_str = ""
    if btc < 1 and btc > 0:
        expanded_display_str = " ({} mbtc".format((btc*1000).quantize(SATOSHI_MBTC_PLACES))
        # following may be useful in future
        # if btc < 0.001:
        #    expanded_display_str += " = {} micro-btc".format(Decimal(btc*1000*1000).quantize(SATOSHI_MICROBTC_PLACES))
        expanded_display_str += ")"
    return "{0} btc{1}".format(btc,expanded_display_str)

def bitcoin_cli_call(cmd="", args="", **optargs):
    # all bitcoind & bitcoin-cli calls to go through this function
    # optargs parsing:
    #  use_bitcoind: if 1 then bitcoind for root cmd rather than bitcoin_cli
    #  call_type: if 1 use subprocess.call instead of .checkoutput
    #  stdout or stderr: if passed here then pass along to subprocess calls
    # defaults paramters: bitcoin_cli, subprocess.check_output, shell=True
    daemon_or_client = bitcoind if optargs.get('use_bitcoind', None) is 1 else bitcoin_cli
    if cmd is not "": cmd = " {0}".format(cmd)
    if args is not "": args = " {0}".format(args)
    full_cmd = "{0}{1}{2}".format(daemon_or_client, cmd, args)
    subprocess_args = { 'shell': True }
    verbose("bitcoin cli call:\n  {0}\n".format(full_cmd))
    for var in ('stdout', 'stderr'):
        if var in optargs: subprocess_args.update({ var: optargs.get(var) })

    if optargs.get('call_type', None) is 1:
        cmd_output = subprocess.call(full_cmd, **subprocess_args)
    else:
        cmd_output = subprocess.check_output(full_cmd, **subprocess_args)
    verbose("bitcoin cli call output:\n  {0}\n".format(cmd_output))
    return cmd_output

def create_unsigned_transaction(source_address, destinations, redeem_script, input_txs):
    """
    Returns a hex string representing an unsigned bitcoin transaction
    returns => <string>

    source_address: <string> input_txs will be filtered for utxos to this source address
    destinations: {address <string>: amount<string>} dictionary mapping destination addresses to amount in BTC
    redeem_script: <string>
    input_txs: List<dict> List of input transactions in dictionary form (bitcoind decoded format)
    """
    ensure_bitcoind_running()

    # prune destination addresses sent 0 btc
    for address, value in destinations.items():
        if value == "0":
            del destinations[address]

    # For each UTXO used as input, we need the txid and vout index to generate a transaction
    inputs = []
    for tx in input_txs:
        utxos = get_utxos(tx, source_address)
        txid = tx["txid"]

        for utxo in utxos:
            inputs.append({
                "txid": txid,
                "vout": int(utxo["n"])
            })

    argstring = "'{0}' '{1}'".format(
        json.dumps(inputs), json.dumps(destinations))

    tx_unsigned_hex = bitcoin_cli_call("createrawtransaction", argstring).strip()

    return tx_unsigned_hex


def sign_transaction(source_address, keys, redeem_script, unsigned_hex, input_txs):
    """
    Creates a signed transaction
    output => dictionary {"hex": transaction <string>, "complete": <boolean>}

    source_address: <string> input_txs will be filtered for utxos to this source address
    keys: List<string> The private keys you wish to sign with
    redeem_script: <string>
    unsigned_hex: <string> The unsigned transaction, in hex format
    input_txs: List<dict> A list of input transactions to use (bitcoind decoded format)
    """

    # For each UTXO used as input, we need the txid, vout index, scriptPubKey, amount, and redeemScript
    # to generate a signature
    inputs = []
    for tx in input_txs:
        utxos = get_utxos(tx, source_address)
        txid = tx["txid"]
        for utxo in utxos:
            inputs.append({
                "txid": txid,
                "vout": int(utxo["n"]),
                "amount": utxo["value"],
                "scriptPubKey": utxo["scriptPubKey"]["hex"],
                "redeemScript": redeem_script
            })

    argstring_2 = "{0} '{1}' '{2}'".format(
        unsigned_hex, json.dumps(inputs), json.dumps(keys))
    signed_hex = bitcoin_cli_call("signrawtransaction", argstring_2).strip()

    signed_tx = json.loads(signed_hex)
    return signed_tx

def num_required_keys_from_redeem(redeem_script):
    decoded_redeem_script = json.loads(bitcoin_cli_call("decodescript",redeem_script))
    return decoded_redeem_script["reqSigs"]

def num_cur_signatures_from_witness(decoded_tx_witness):
    # assumptions re *decoded* witness data:
    #   first element blank
    #   next elements: signatures (if signed) or blank (if unsigned)
    #   last element redeem_script
    # so to get current number of sigs iterate through elements and see if blank, ignoring 1st & last
    num_sigs = 0
    for i in range(1, (len(decoded_tx_witness) - 1)):
        if not decoded_tx_witness[i]:
            verbose("\nsignature place #{} is blank (unsigned)".format(i))
        else:
            verbose("\nsignature place #{0}: {1}".format(i,decoded_tx_witness[i]))
            num_sigs+=1
    return num_sigs
    
def revise_vsize_if_missing_keys(vsize, size, num_cur_sigs, num_req_sigs):
    remaining_keys = int(num_req_sigs) - int(num_cur_sigs)
    # key size: 73 bytes (142 hex chars; 72 bytes but then add 1 for opcode)
    key_added_size = 73
    stripped_size = ( (vsize * 4) - size ) / 3
    final_size = size + (remaining_keys * key_added_size)
    final_vsize = ((3 * stripped_size) + final_size) / 4

    verbose("\nrevise fee vars:\n  num_cur_sigs: {0}\n  num_req_sigs: {1}\n  calc'd remaining_keys: {2}\n  vsize: {3}\n  size: {4}\n  stripped_size: {5}\n  const key size: {6}\n  final_size: {7}\n  final (revised) vsize: {8}".format(num_cur_sigs, num_req_sigs, remaining_keys, vsize, size, stripped_size, key_added_size, final_size, final_vsize))

    return final_vsize

def get_fee_interactive(source_address, keys, destinations, redeem_script, input_txs):
    """
    Returns a recommended transaction fee, given market fee data provided by the user interactively
    Because fees tend to be a function of transaction size, we build the transaction in order to
    recomend a fee.
    return => <Decimal> fee value

    Parameters:
      source_address: <string> input_txs will be filtered for utxos to this source address
      keys: A list of signing keys
      destinations: {address <string>: amount<string>} dictionary mapping destination addresses to amount in BTC
      redeem_script: String
      input_txs: List<dict> List of input transactions in dictionary form (bitcoind decoded format)
      fee_basis_satoshis_per_byte: <int> optional basis for fee calculation
    """

    MAX_FEE = .005  # in btc.  hardcoded limit to protect against user typos

    ensure_bitcoind_running()

    approve = False
    while not approve:
        print "\nEnter fee rate."
        fee_basis_satoshis_per_byte = int(raw_input("Satoshis per vbyte: "))

        unsigned_tx = create_unsigned_transaction(
            source_address, destinations, redeem_script, input_txs)

        signed_tx = sign_transaction(source_address, keys,
                                     redeem_script, unsigned_tx, input_txs)

        decoded_tx = json.loads(bitcoin_cli_call("decoderawtransaction", signed_tx["hex"]))
        
        # estimate tx size - depends on whether have all required sigs now
        if not signed_tx["complete"]:
            verbose("transaction incomplete so revising fee estimate to account for missing keys")
            # get total number of keys signing up to & including this point
            num_cur_sigs = num_cur_signatures_from_witness(decoded_tx["vin"][0]["txinwitness"])
            # get total number of keys required (m in the m-of-n)
            num_req_sigs = num_required_keys_from_redeem(redeem_script)
            
            size = revise_vsize_if_missing_keys(decoded_tx["vsize"], decoded_tx["size"], num_cur_sigs, num_req_sigs)
        else:
            verbose("transaction complete: have enough keys to fully-sign transaction")
            size = decoded_tx["vsize"]
        # end estimate tx size block

        fee = size * fee_basis_satoshis_per_byte
        fee = satoshi_to_btc(fee)

        if fee > MAX_FEE:
            print "Calculated fee ({}) is too high. Must be under {}.".format(btc_display(fee), btc_display(MAX_FEE))
        else:
            print "\nBased on the provided rate, the fee will be {}.".format(btc_display(fee))
            confirm = yes_no_interactive()

            if confirm:
                approve = True
            else:
                print "\nFee calculation aborted. Starting over..."

    return fee

def withdrawal_amounts_interactive(input_amount, fee, dest_address, source_address):
    # inputs: input_amount & fee (to get amts) + dest_address, source address (for display)
    # outputs: withdrawal_amount, change_amount
    print "\nPlease enter the decimal amount (in bitcoin) to withdraw to the destination address."
    print "\nExample: For 2.3 bitcoins, enter \"2.3\"."
    print "\nAfter a fee of {0}, you have {1} available to withdraw.".format(btc_display(fee), btc_display(input_amount - fee))
    print "\n*** Technical note for experienced Bitcoin users:  If the withdrawal amount & fee are cumulatively less than the total amount of the unspent transactions, the remainder will be sent back to the same cold storage address as change. ***\n"
    withdrawal_amount = raw_input(
        "Amount to send to {0} (leave blank to withdraw all funds stored in these unspent transactions): ".format(dest_address))
    if withdrawal_amount == "":
        withdrawal_amount = input_amount - fee
    else:
        withdrawal_amount = Decimal(withdrawal_amount).quantize(SATOSHI_PLACES)

    if fee + withdrawal_amount > input_amount:
        print "Error: fee + withdrawal amount greater than total amount available from unspent transactions"
        raise Exception("Output values greater than input value")

    change_amount = input_amount - withdrawal_amount - fee
    change_amount = zero_less_than_satoshi(change_amount)

    if change_amount > 0:
        print "{0} being returned to cold storage address address {1}.".format(btc_display(change_amount), source_address)
    return withdrawal_amount, change_amount

################################################################################################
#
# QR code helper functions
#
################################################################################################

def write_and_verify_qr_code(name, filename, data):
    """
    Write a QR code and then read it back to try and detect any tricksy malware tampering with it.

    name: <string> short description of the data
    filename: <string> filename for storing the QR code
    data: <string> the data to be encoded
    """

    QR_SUFFIX = ".png"
    script_root = os.path.dirname(os.path.abspath(__file__))
    qr_increment = ""

    i = 2
    while(True):
        qr_path = script_root + "/" + filename + qr_increment + QR_SUFFIX
        if not os.path.exists(qr_path): break
        verbose("\nQR exists at: {}, thus incrementing file suffix".format(qr_path))
        qr_increment = str(i)
        i += 1

    subprocess.call("qrencode -o {0} {1}".format(qr_path, data), shell=True)
    check = subprocess.check_output(
        "zbarimg --set '*.enable=0' --set 'qr.enable=1' --quiet --raw {}".format(qr_path), shell=True)

    if check.strip() != data:
        print "********************************************************************"
        print "WARNING: {} QR code could not be verified properly. This could be a sign of a security breach.".format(name)
        print "********************************************************************"

    print "QR code for {0} written to {1}".format(name, filename + qr_increment + QR_SUFFIX)


################################################################################################
#
# User sanity checking
#
################################################################################################

def yes_no_interactive():
    def confirm_prompt():
        return raw_input("Confirm? (y/n): ")

    confirm = confirm_prompt()

    while True:
        if confirm.upper() == "Y":
            return True
        if confirm.upper() == "N":
            return False
        else:
            print "You must enter y (for yes) or n (for no)."
            confirm = confirm_prompt()

def safety_checklist():

    checks = [
        "Are you running this on a computer WITHOUT a network connection of any kind?",
        "Have the wireless cards in this computer been physically removed?",
        "Are you running on battery power?",
        "Are you running on an operating system booted from a USB drive?",
        "Is your screen hidden from view of windows, cameras, and other people?",
        "Are smartphones and all other nearby devices turned off and in a Faraday bag?"]

    for check in checks:
        answer = raw_input(check + " (y/n)?")
        if answer.upper() != "Y":
            print "\n Safety check failed. Exiting."
            sys.exit()


################################################################################################
#
# Main "entropy" function
#
################################################################################################


def unchunk(string):
    """
    Remove spaces in string
    """
    return string.replace(" ", "")


def format_chunks(size, string):
    """
    Splits a string into chunks of [size] characters, for easy human readability
    """
    tail = ""
    remainder = len(string) % size
    arr = [string[size * i: size * i + size] for i in range(len(string) / size)]
    body = " ".join(arr)
    if remainder > 0:
        tail = string[-remainder:]
    return body + " " + tail


def entropy(n, length):
    """
    Generate n random strings for the user from /dev/random
    """
    safety_checklist()

    print "\n\n"
    print "Making {} random data strings....".format(n)
    print "If strings don't appear right away, please continually move your mouse cursor. These movements generate entropy which is used to create random data.\n"

    idx = 0
    while idx < n:
        seed = subprocess.check_output(
            "xxd -l {} -p /dev/random".format(length), shell=True)
        idx += 1
        seed = seed.replace('\n', '')
        print "Computer entropy #{0}: {1}".format(idx, format_chunks(4, seed))


################################################################################################
#
# Main "deposit" function
#
################################################################################################

def deposit_interactive(m, n, dice_seed_length=62, rng_seed_length=20):
    """
    Generate data for a new cold storage address (private keys, address, redemption script)
    m: <int> number of multisig keys required for withdrawal
    n: <int> total number of multisig keys
    dice_seed_length: <int> minimum number of dice rolls required
    rng_seed_length: <int> minimum length of random seed required
    """

    safety_checklist()
    ensure_bitcoind_running()

    print "\n"
    print "Creating {0}-of-{1} cold storage address.\n".format(m, n)

    keys = []

    while len(keys) < n:
        index = len(keys) + 1
        print "\nCreating private key #{}".format(index)

        dice_seed_string = read_dice_seed_interactive(dice_seed_length)
        dice_seed_hash = hash_sha256(dice_seed_string)

        rng_seed_string = read_rng_seed_interactive(rng_seed_length)
        rng_seed_hash = hash_sha256(rng_seed_string)

        # back to hex string
        hex_private_key = xor_hex_strings(dice_seed_hash, rng_seed_hash)
        WIF_private_key = hex_private_key_to_WIF_private_key(hex_private_key)

        keys.append(WIF_private_key)

    print "Private keys created."
    print "Generating {0}-of-{1} cold storage address...\n".format(m, n)

    addresses = [get_address_for_wif_privkey(key) for key in keys]
    results = addmultisigaddress(m, addresses)

    print "Private keys:"
    for idx, key in enumerate(keys):
        print "Key #{0}: {1}".format(idx + 1, key)

    print "\nCold storage address:"
    print "{}".format(results["address"])

    print "\nRedemption script:"
    print "{}".format(results["redeemScript"])
    print ""

    write_and_verify_qr_code("cold storage address", "address", results["address"])
    write_and_verify_qr_code("redemption script", "redemption",
                       results["redeemScript"])


################################################################################################
#
# Main "withdraw" function
#
################################################################################################

def withdraw_interactive():
    """
    Construct and sign a transaction to withdaw funds from cold storage
    All data required for transaction construction is input at the terminal
    """

    safety_checklist()
    ensure_bitcoind_running()

    approve = False

    while not approve:
        addresses = {}

        print "\nYou will need to enter several pieces of information to create a withdrawal transaction."
        print "\n\n*** PLEASE BE SURE TO ENTER THE CORRECT DESTINATION ADDRESS ***\n"

        source_address = raw_input("\nSource cold storage address: ")

        if re_sign_mode is not 1:
            redeem_script = raw_input("\nRedemption script for source cold storage address: ")
            dest_address = raw_input("\nDestination address: ")
            num_tx = int(raw_input("\nHow many unspent transactions will you be using for this withdrawal? "))
        else:
            unsigned_tx, redeem_script, dest_address, change_amount, withdrawal_amount, num_tx  = parse_part_signed_tx(source_address)

        addresses[source_address] = 0
        addresses[dest_address] = 0

        input_txs = []
        utxos = []
        utxo_sum = Decimal(0).quantize(SATOSHI_PLACES)

        while len(input_txs) < num_tx:

            # start block to be replaced by following comment line
            #   hex_tx = get_raw_tx_interactive("For input transaction #{}".format(len(input_txs) + 1))
            # not implementing now because will break testing
            print "\nPlease paste raw transaction #{} (hexadecimal format) with unspent outputs at the source address".format(len(input_txs) + 1)
            print "OR"
            print "input a filename located in the current directory which contains the raw transaction data"
            print "(If the transaction data is over ~4000 characters long, you _must_ use a file.):"

            hex_tx = raw_input()
            if os.path.isfile(hex_tx):
                hex_tx = open(hex_tx).read().strip()
            # end block to be replaced

            tx = json.loads(bitcoin_cli_call("decoderawtransaction", hex_tx))
            input_txs.append(tx)
            utxos += get_utxos(tx, source_address)

        if len(utxos) == 0:
            print "\nTransaction data not found for source address: {}".format(source_address)
            sys.exit()
        else:
            print "\nTransaction data found for source address."

            for utxo in utxos:
                value = Decimal(utxo["value"]).quantize(SATOSHI_PLACES)
                utxo_sum += value

            print "TOTAL unspent amount for this raw transaction: {}".format(btc_display(utxo_sum))

        print "\nHow many private keys will you be signing this transaction with? "
        key_count = int(raw_input("#: "))

        keys = []
        while len(keys) < key_count:
            key = raw_input("Key #{0}: ".format(len(keys) + 1))
            keys.append(key)

        ###### fees, amount, and change #######

        input_amount = utxo_sum

        if re_sign_mode is not 1:
            fee = get_fee_interactive(
                source_address, keys, addresses, redeem_script, input_txs)
            check_fee_to_input_amt(fee, input_amount)
            withdrawal_amount, change_amount = withdrawal_amounts_interactive(input_amount, fee, dest_address, source_address)
        else:
            fee = input_amount - withdrawal_amount - change_amount
            check_fee_to_input_amt(fee, input_amount)

        addresses[dest_address] = str(withdrawal_amount)
        addresses[source_address] = str(change_amount)

        # check data
        print "\nIs this data correct?"
        print "*** WARNING: Incorrect data may lead to loss of funds ***\n"

        print "{} in unspent supplied transactions".format(btc_display(input_amount))
        for address, value in addresses.iteritems():
            if address == source_address:
                print "{0} going back to cold storage address {1}".format(btc_display(value), address)
            else:
                print "{0} going to destination address {1}".format(btc_display(value), address)
        print "Fee amount: {0}".format(btc_display(fee))
        print "\nSigning with private keys: "
        for key in keys:
            print "{}".format(key)

        print "\n"
        confirm = yes_no_interactive()

        if confirm:
            approve = True
        else:
            print "\nProcess aborted. Starting over...."

    #### Calculate Transaction ####
    print "\nCalculating transaction...\n"

    if re_sign_mode is not 1:
        unsigned_tx = create_unsigned_transaction(
            source_address, addresses, redeem_script, input_txs)

    signed_tx = sign_transaction(source_address, keys,
                                 redeem_script, unsigned_tx, input_txs)

    print "\nSufficient private keys to execute transaction?"
    print signed_tx["complete"]

    print "\nRaw signed transaction (hex):"
    print signed_tx["hex"]

    print "\nTransaction fingerprint (md5):"
    print hash_md5(signed_tx["hex"])

    write_and_verify_qr_code("transaction", "transaction", signed_tx["hex"])


################################################################################################
#
# main function
#
# Show help, or execute one of the three main routines: entropy, deposit, withdraw
#
################################################################################################

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('program', choices=[
                        'entropy', 'create-deposit-data', 'create-withdrawal-data', 'sign-transaction'])

    parser.add_argument("--num-keys", type=int,
                        help="The number of keys to create random entropy for", default=1)
    parser.add_argument("-d", "--dice", type=int,
                        help="The minimum number of dice rolls to use for entropy when generating private keys (default: 62)", default=62)
    parser.add_argument("-r", "--rng", type=int,
                        help="Minimum number of 8-bit bytes to use for computer entropy when generating private keys (default: 20)", default=20)
    parser.add_argument(
        "-m", type=int, help="Number of signing keys required in an m-of-n multisig address creation (default m-of-n = 1-of-2)", default=1)
    parser.add_argument(
        "-n", type=int, help="Number of total keys required in an m-of-n multisig address creation (default m-of-n = 1-of-2)", default=2)
    parser.add_argument('--testnet', type=int, help=argparse.SUPPRESS)
    parser.add_argument('-v', action='store_const', default=0, dest='verbose_mode', const=1,
                        help='increase output verbosity')
    args = parser.parse_args()

    verbose_mode = args.verbose_mode

    global bitcoind, bitcoin_cli, wif_prefix
    cli_args = "-testnet -rpcport={} -datadir=bitcoin-test-data ".format(args.testnet) if args.testnet else ""
    wif_prefix = "EF" if args.testnet else "80"
    bitcoind = "bitcoind " + cli_args
    bitcoin_cli = "bitcoin-cli " + cli_args

    if args.program == "entropy":
        entropy(args.num_keys, args.rng)

    if args.program == "create-deposit-data":
        deposit_interactive(args.m, args.n, args.dice, args.rng)

    if args.program == "create-withdrawal-data":
        withdraw_interactive()

    if args.program == "sign-transaction":
        # re-sign a partially signed transaction with another signature - for cold storage withdrawal
        print "\n\nSequential signing of transactions supports ONLY Segwit wallets/transactions. This will not work with non-segwit wallets/transactions. Proceeding with non-segwit wallets/transactions RISKS LOSS OF FUNDS. Please confirm using segwit to proceed."
        if not yes_no_interactive():
            print "\ncould not confirm segwit to proceed with sequential transaction signing...exiting"
            sys.exit()
        re_sign_mode = 1
        withdraw_interactive()
