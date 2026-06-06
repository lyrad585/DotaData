import os
import sys

VPN_ENABLED = True if os.getenv("VPN_ENABLED").lower() == "true" else False
if VPN_ENABLED:
    VPN_PATH = os.getenv(r"VPN_PATH", r"C:\Program Files\Windscribe\windscribe-cli.exe")
    VPN_LOCATIONS = os.getenv("VPN_LOCATIONS", "Not set")
    VPN_LOCATIONS = VPN_LOCATIONS.split(",") if VPN_LOCATIONS else []
    VPN_LOCATION_START_INDEX = int(os.getenv("VPN_LOCATION_START_INDEX", 0))
CHECK_OPENDOTA = True if os.getenv("CHECK_OPENDOTA").lower() == "true" else False
SSAP = True if os.getenv("SYNC_STRATZ_ACCOUNT_PROFILE_FLAG").lower() == "true" else False
SSMD = True if os.getenv("SYNC_STRATZ_MATCH_DETAILS_FLAG").lower() == "true" else False

def opendota():

    def sync_opendota_account_profile():
        print(f"***************************\n{sys._getframe().f_code.co_name}\n***************************")
        print(locals())
        print("--------------------------------------------------------------------")
        print(globals())
        print("--------------------------------------------------------------------")

    SOAP = True if os.getenv("SYNC_OPENDOTA_ACCOUNT_PROFILE_FLAG").lower() == "true" else False
    SOAM = True if os.getenv("SYNC_OPENDOTA_ACCOUNT_MATCHES_FLAG").lower() == "true" else False
    SOMI = True if os.getenv("SYNC_OPENDOTA_MATCH_IDS_FLAG").lower() == "true" else False
    print(f"***************************\n{sys._getframe().f_code.co_name}\n***************************")
    print(locals())
    print("--------------------------------------------------------------------")
    print(globals())
    print("--------------------------------------------------------------------")

    if SOAP:
        sync_opendota_account_profile()

def main():
    print(f"***************************\n{sys._getframe().f_code.co_name}\n***************************")
    print(locals())
    print("--------------------------------------------------------------------")
    print(globals())
    print("--------------------------------------------------------------------")
    if CHECK_OPENDOTA:
        opendota()

if __name__ == "__main__":
    print(f"***************************\n{sys._getframe().f_code.co_name}\n***************************")
    print(locals())
    main()
