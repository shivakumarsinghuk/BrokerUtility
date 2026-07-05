# -*- coding: utf-8 -*-
"""
Zerodha Kite Connect - Historical Data

"""
import os
from DataTypes.login_types import *
from DataTypes.trade_data import *
from ..broker_platform.fyers import *
from ..broker_platform.zebu import *
from ..broker_platform.kite import *


#defines

#Key words
UM_KW_BROKER = "broker"
UM_KW_USER_NAME = "user_name"
UM_KW_CLIENT_ID = "client_id"
UM_KW_SECRET_ID = "secret_id"
UM_KW_PIN = "pin"
UM_KW_TOTP = "totp"
UM_KW_PHONE_NO = "phone_no"
UM_KW_ACCESS_TOKEN = "zaccess_token"
UM_KW_REFRESH_TOKEN = "zrefresh_token"
UM_KW_STOCK_LIST = "stock_list"
UM_KW_OPTION_LIST = "option_list"
UM_KW_TRADE_DAYS = "trade_days"

@dataclass
class utility_object_data:
    def __init__(self, broker_utility, user_name, stock_list, option_list, trade_days):
        self.broker_utility = broker_utility
        self.user_name = user_name
        self.stock_list = stock_list
        self.option_list = option_list
        self.trade_days = trade_days

    def get_user_name(self):
        return self.user_name

    def get_broker_utility(self):
        return self.broker_utility

    def get_stock_list(self):
        return self.stock_list

    def get_option_list(self):
        return self.option_list

    def get_trade_days(self):
        return self.trade_days

#Utility manager class is responsible to manager the utility objects and it provides
#interfaces to get the utility object
class utility_manager:
    def __init__(self):
        self.dict_utility_function = {"fyers":self.get_fyers_utility_object,
                                      "zerodha":self.get_kite_utility_object,
                                      "zebumynt":self.get_zebu_utility_object}
        self.dict_utility = {}

    def get_utility_object(self, broker_data:LogInData):
        #check whether dict utility function available
        if broker_data.user_id in self.dict_utility:
            #get the object from dictionary and return
            print("User name already exist: ", broker_data.user_id)
        else:
            if broker_data.broker.lower() in self.dict_utility_function:
                self.dict_utility_function[broker_data.broker.lower()](user_name=broker_data.user_id,\
                                                                client_id=broker_data.api_key,\
                                                                secret_id=broker_data.api_secret_key,\
                                                                pin=broker_data.password,\
                                                                totp=broker_data.totp_key,
                                                                phone_no=broker_data.phone_no,\
                                                                refresh_token="")
                #add the object to dictionary
                obj_utility_object_data = utility_object_data(broker_utility=f"obj_trade_utility{broker_data.user_id}", stock_list=[], option_list=[], trade_days=[], user_name=broker_data.user_id)
                self.dict_utility[broker_data.user_id] = obj_utility_object_data
                globals()[f"broker_utility_data{broker_data.user_id}"] = globals()["utility_object_data"](globals()[f"obj_trade_utility{broker_data.user_id}"], stock_list=[], option_list=[], trade_days=[], user_name=broker_data.user_id)
        return globals()[f"broker_utility_data{broker_data.user_id}"]

    def get_fyers_utility_object(self, user_name="", client_id="", secret_id="", pin="", totp="", phone_no="", refresh_token=""):
        globals()[f"obj_trade_utility{user_name}"] = fyers_utitlity(user_name=user_name,
                                                                    client_id=client_id,
                                                                    secret_id=secret_id,
                                                                    pin=pin,
                                                                    totp=totp,
                                                                    phone_no=phone_no,
                                                                    refresh_token=refresh_token)

    def get_kite_utility_object(self, user_name="", client_id="", secret_id="", pin="", totp="", phone_no="", refresh_token = ""):
        globals()[f"obj_trade_utility{user_name}"] = kite_utitlity(user_name=user_name,
                                                                   client_id=client_id,
                                                                   secret_id=secret_id,
                                                                   pin=pin,
                                                                   totp=totp,
                                                                   phone_no=phone_no)

    def get_zebu_utility_object(self, user_name="", client_id="", secret_id="", pin="", totp="", phone_no="", refresh_token = ""):
        globals()[f"obj_trade_utility{user_name}"] = zebumynt_utitlity(user_name=user_name,
                                                                   client_id=client_id,
                                                                   secret_id=secret_id,
                                                                   pin=pin,
                                                                   totp=totp,
                                                                   phone_no=phone_no)


