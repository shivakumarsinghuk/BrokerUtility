from DataTypes.login_types import *
from pal.utility_manager import *


obj_utility_manager = utility_manager()
#For ZEBUMYNT

loginData = LogInData(broker="ZEBUMYNT",
                                            user_id="ZVK0116",
                                            password="Zeb#1mar81",
                                            api_key="", 
                                            api_secret_key="XugYc8TC2R6N5Z7v56Pd7347zQaRvE73",
                                            phone_no="1c:91:80:e5:fa:5a",
                                            totp_key="04041986")


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
