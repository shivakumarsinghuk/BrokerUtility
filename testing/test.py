import datatypes.login_types
from pal.utility_manager import *
from datatypes.login_types import *


obj_utility_manager = utility_manager()
#For ZEBUMYNT
'''
loginData = datatypes.login_types.LogInData(broker="ZEBUMYNT", 
                                            user_id=<user_id>, 
                                            password=<password>, 
                                            api_key="", 
                                            api_secret_key=<api_secret_key>, 
                                            phone_no=<mac address>,
                                            totp_key=<DOB>)
'''

#For Fyers
'''
loginData = datatypes.login_types.LogInData(broker="FYERS",
                                            user_id=<user_id>,
                                            password=<xxxx - Four digit pin>,
                                            api_key=<api_id>,
                                            api_secret_key=<app_secret>,
                                            phone_no=<phone_no>,
                                            totp_key=<TOTP_KEY>)
                                            
Manually token URL should be pasted in chrome and provide the credentials. 
Copy the url from address box and paste in python
'''

#For Zerodha
'''
loginData = datatypes.login_types.LogInData(broker="ZERODHA",
                                            user_id=<user_id>,
                                            password=<password>,
                                            api_key=<api_key>,
                                            api_secret_key=<app_secret>,
                                            phone_no=<phone_no>,
                                            totp_key=<TOTP_KEY>)
'''
obj_utility_manager.get_utility_object(loginData)
