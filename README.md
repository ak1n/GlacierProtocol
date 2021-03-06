# Glacier
Glacier is a protocol for secure cold storage of bitcoins.
[https://www.glacierprotocol.org](https://www.glacierprotocol.org)

* this is a fork of Glacier by ak1n
* modifications in this fork need further auditing and testing
* protocol documentation to go along with proposed protocol modifications not yet completed

## ak1n modifications
* source repository: https://github.com/GlacierProtocol/GlacierProtocol
* ak1n modification fork: https://github.com/ak1n/GlacierProtocol

* this master branch should contain the "done pending review" mainline glacier items below

### features / branches for proposed integration w mainline glacier
* complete:
  1. **bitcoin-cli-fn-take2** consolidation of bitcoin cli calls - allows easier debugging w subsequent mods
  2. **verbose-mode**: `-v` argument. output includes bitcoin-cli calls. useful in debugging
  3. **sequential-signing**
    * add support for sequential-signing/re-signing: provide another signature to partially-signed transaction
    * invoke feature within modified withdrawal function via CLI `sign-transaction` argument toggle
    * make testing files added
    * needs upgrade of fee transaction estimation to work best
  4. **fix-fees**: adjust fee estimate in sequential signing to account for eventual complete-key (m keys) signage
  5. **btc-display-consolidate**: centralized processing of BTC display w mBTC
  6. **qr-increment**: increment qr filename to allow multiple transactions offline
    * modify qr function to increment, alter calls to exclude suffix, and in makefile remove PNGs w tests to pass make
  7. **single-safety-confirm**: `-s` flag toggles one safety checklist confirmation input (useful for testing on mainnet)
  8. merge-in of upstream v17 and hex-patch commits (into master) 1/16/19
  9. **cli-fn-mods**: improve bitcoin cli call handling - part 1
  10. **hodler-work-integration-cli-calls**: many improvements in bitcoin-cli call functions - including specifically conversion to using lists rather than string args. see [bitcoinhodler's **clifunc**](https://github.com/bitcoinhodler/GlacierProtocol/tree/clifunc)
  11. **better-booleans2**: streamline bools (0/1 to False/True)

### features / branches for fork
* under revision:
  * tailsOS supprt
  * veracrypt support: for digital, rather than paper, storage of keys
  * setup function
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
   * veracrypt specific functions:
      * gui install as above - ***required for volume creation only***
      * note that do NOT need to install for opening veracrypt volumes
    * open & close veracrypt volume functions
* once above complete: formal auditing

### protocol deviations (for eventual full-fork)
* keys on digital storage media
  * e.g. keepassx database within a veracrypt volume
* transaction signing: sequentially at distinct physical locations
* bitcoin acquired directly rather than via ubuntu PPA
  * https://bitcoin.org/bin/bitcoin-core-0.17.1/bitcoin-0.17.1-x86_64-linux-gnu.tar.gz
  * rationale: why introduce intermediary? reduce complexity
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
  * use more secure Tails OS (Ubuntu is not equivalent even offline)
    * superior to Ubuntu regardless whether online/offline or paper/digital wallets
    * tails under ongoing greater security/privacy scrutiny vs. e.g. Ubuntu
  * acknowledge theoretical cons:
    * potential key loss through:
      * forgetting/losing passwords for key containers/media
      * damage specific to digital media (e.g. EMP)
    * expansion of digital attack surface by storing keys digitally

### testing stages outline
* make testing
* main-network btc transfer testing
* formal auditing
  * code
  * protocol / opsec
  * likely multiple phases/revisions

## ak1n public pgp / gpg key
```
-----BEGIN PGP PUBLIC KEY BLOCK-----

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
h+UT7Bc2Nu/aqmrxC4YFZA==
=78MB
-----END PGP PUBLIC KEY BLOCK-----

```
