# Glacier
Glacier is a protocol for secure cold storage of bitcoins.
[https://www.glacierprotocol.org](https://www.glacierprotocol.org)

* this is a fork of Glacier by ak1n
* modifications in this fork need further auditing and testing
* protocol documentation to go along with software modifications not yet completed

## ak1n modifications
* source repository: https://github.com/GlacierProtocol/GlacierProtocol
* ak1n modification fork: https://github.com/ak1n/GlacierProtocol

### features / branches
* **base-upgrades**
  * consolidate most bitcoin-cli calls into dedicated function
  * verbose mode: `-v` argument. output includes showing most bitcoin-cli calls
  * qr upgrades
    * allow generation of multiple qr's without overwriting: increment filename with file/directory checking
    * allow generation of qr's from script w `qr-code -q DATA`
      * may be useful for more secure misc data transfer from q-environment in addition to debugging
  * single confirm for safety checklist
    * remove repeated confirmations for safety checklist
    * add global toggle that allows overriding this change
  * decrease verbosity of safety checklist
  * mBTC display when showing fees
* **sequential-sign**
  * add support for sequential-signing/re-signing: provide another signature to partially-signed transaction
  * invoke feature within modified withdrawal function via CLI `sign-transaction` argument toggle
* **tails-veracrypt**
  * setup function for using tails OS:
    * invocation arguments: `setup -t` (latter for tails in event setup applied to other distros)
    * installs deb packages, bitcoin binaries, and (w CLI argument) veracrypt installer
    * optionally receives arguments for software directories, otherwise looks at default locations as follows
    * deb packages
      * default directory: `/media/amnesia/apps/tails_apps`
      * optional override argument: `--appdir=CUSTOM_DIR`
    * bitcoin binaries
      * default btc root directory: `/media/amnesia/apps/tails_apps/bitcoin-0.17.0`
      * optional override argument: `--btcdir=CUSTOM_DIR`
    * optional veracrypt instal via gui installer launch
      * default directory: `/media/amnesia/apps/tails_apps/veracrypt-1.23-setup/veracrypt-1.23-setup-gui-x64`
      * optional override argument: `--veracrypt-dir=CUSTOM_DIR`
  * veracrypt support
    * gui install as above - ***required for volume creation only***
      * note that do NOT need to install for opening veracrypt volumes
    * open & close veracrypt volume functions
* **proposed-mainline-merger**
  * incorporates base-upgrades, sequential-sign, tails-veracrypt, and minor merger conflict resolution
* **master**: same as proposed-mainline-merger except has this README

### protocol deviations
* keys on digital storage media
  * e.g. keepassx database within a veracrypt volume
* transaction signing: sequentially at distinct physical locations
* bitcoin acquired directly rather than via ubuntu PPA
  * https://bitcoin.org/bin/bitcoin-core-0.17.1/bitcoin-0.17.1-x86_64-linux-gnu.tar.gz
* Tails OS over ubuntu - deb packages needed:
  * deb packages:`zbar-tools qrencode gnome-tweak-tool`
    * note: I include gnome-tweak-tool because the default trackpad settings drive me insane (I recommend tweak: Default -> Fingers)
    * move files to appropriate USB directory: `cp /var/cache/apt/archives*.deb /media/amnesia/apps/tails_apps/`
* use semi-secure laptop rather than cellphone for qr-code transfers
  * multiple software options
    * zbarcam: receive on q/offline-machine, receive on online machine
    * qrencode: send from online machine. `qrencode -o FILENAME DATA`
    * glacier script: on offline or online machine for generating qr's
    * qtqr: alternative to using above on online machine
* summary of rationale for above (non-detailed):
  * reduce physical location attack vector
    * don't co-localize keys for withdrawal - use sequential sign
    * don't use media that store keys in plaintext (paper) - use encrypted volumes
  * use more secure OS (Ubuntu is not equivalent even offline)
  * acknowledge theoretical cons:
    * potential key loss through:
      * forgetting/losing passwords for key containers/media
      * damage specific to digital media (e.g. EMP)
    * expansion of digital attack surface by storing keys digitally

### testing performed
* note: testing performed for related functions of each main branch, then for merged master branch
* boot from tails USB - enable adminstrator password on boot
* insert app USB
* 1st boot: online
  * download deb packages, bitcoin, and veracrypt & load into apps folder as per above
  * reboot
* subsequent boots: offline
* run glacier setup script for tails: `./glacierscript.py setup -t --veracrypt`
  * click through verascript installer GUI
  * omit `--veracrypt` if previously created volume
* change UI settings if needed (for me settings -> disable tap to click, disable "natural" scrolling. tweak settings as above)
* veracrypt testing:
  * create veracrypt volume using gui (having run installer for related boot w `--veracrypt`)
  * veracrypt-open & veracrypt-close arguments
* create fake dice entropy
* create computer entropy: `./glacierscript.py entropy --num-keys 4`
* create cold storage address with entropy (used 2 of 4 setup)
  * for testing store wallet info in either veracrypt volume or text file
* use zbarcam to transfer cold storage address via qr
* fund cold storage wallet address (e.g. electrum w fee selection using https://bitcoinfees.21.co/api/v1/fees/recommended)
* get hex of funding transaction (via https://blockchain.info/tx/transaction_id_here?format=hex)
* transfer from online to offline machine via qr:
  * tx hex
  * btc addresses to receive coins back to
* perform withdrawal using re-sign for partial and then total total balance - for each:
  * create withdrawal transaction and sign with only 1 key: `./glacierscript.py create-withdrawal-data`
  * re-sign transaction w `sign-transaction`, providing additional key to complete signing
  * transfer signed tx hex to online computer via qr
  * verify then broadcast tx via https://coinb.in/#verify
* note that in between withdrawals need to re-acquire funding tx hex that has been partially depleted so glacier script can work with updated balance amounts (otherwise transferring more than have or attempt to txfer non-existent balance)

## ak1n public pgp / gpg key
```
-----BEGIN PGP PUBLIC KEY BLOCK-----

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
=vKas
-----END PGP PUBLIC KEY BLOCK-----
```
