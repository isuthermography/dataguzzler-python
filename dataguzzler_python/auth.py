# This is a ridiculously simple authentication module

class password_auth:
    accts = None
    def __init__(self,*accts):
        self.accts=accts
        pass

    def auth(self,username,password):
        matches = [ username==acctname and password==acctpasswd for (acctname,acctpasswd) in self.accts ]
        if any(matches):
            return (200,"AUTH_SUCCESS")
        return (510,"AUTH_FAILURE")
    
    
    pass

def password_acct(username,password):
    return (username,password)

#class password_acct:
#    username = None
#    password = None
#
#    def __init__(self,username,password):
#        self.username=username
#        self.password=password
#        pass
#    pass
