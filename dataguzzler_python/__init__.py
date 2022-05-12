import sys

from .auth import password_auth,password_acct

def get_snde_or_none():
    if "spatialnde2" in sys.modules:        
        import spatialnde2
        return spatialnde2
    return None
