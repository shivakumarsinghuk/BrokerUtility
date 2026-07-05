# -*- coding: utf-8 -*-
"""
Zerodha Kite Connect - Historical Data

"""
import time

from kiteconnect import KiteConnect
import logging
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
import pandas as pd
from DataTypes.trade_data import *
import traceback
from pyotp import TOTP
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from DataTypes.defines import *
import datetime as dt

#defines
KITE_API_RETRY_COUNT = 3
KITE_API_RETRY_TIME = 1

#Key words
UM_KW_BROKER = "broker"
UM_KW_USER_NAME = "user_name"
UM_KW_CLIENT_ID = "client_id"
UM_KW_SECRET_ID = "secret_id"
UM_KW_PIN = "pin"
UM_KW_TOTP = "totp"


def is_monthly_expiry(self, p_str_option_name):
    option_index = get_position_of_first_digit(p_str_option_name)
    if p_str_option_name[0:option_index] in self.dict_monthly_expiry_date:
        lst_monthly_expiry_date = self.dict_monthly_expiry_date[p_str_option_name[0:option_index]].split("-")
        monthly_expiry_date = lst_monthly_expiry_date[0] + lst_monthly_expiry_date[1].upper() + lst_monthly_expiry_date[
                                                                                                    2][2:]
        if p_str_option_name[option_index:(option_index + 7)] \
                == monthly_expiry_date:
            return True
        else:
            return False
    else:
        return True

class kite_utitlity:
    def __init__(self,user_name, client_id, secret_id, pin, totp, phone_no):
        #generate trading session
        try:
            self.user_name = user_name
            self.api_key = client_id
            self.secret_key = secret_id
            self.pword = pin
            self.totp = totp

            #create kite connect object
            self.kite = KiteConnect(api_key=self.api_key)

            #get the request token
            self.request_token = self.__get_request_token()
            data = self.kite.generate_session(self.request_token, api_secret=self.secret_key)
            self.access_token = data["access_token"]
           # self.access_token = self.kite.generate_session(self.request_token, api_secret=self.api_key)["access_token"]
            #set the access token
            self.kite.set_access_token(self.access_token)
            #get dump of all NSE instruments
            self.instrument_dump = self.kite.instruments("NSE")
            self.instrument_df = pd.DataFrame(self.instrument_dump)
        except:
            print("Exception in kite utility constructor")

    #session token apis
    def __get_request_token(self):
        try:
            driver = webdriver.Chrome()
            driver.get(self.kite.login_url())
            driver.implicitly_wait(10)
            print("Entertring")
            username = driver.find_element(By.ID, "userid")
            password = driver.find_element(By.ID, "password")
            username.send_keys(self.user_name)
            password.send_keys(self.pword)
            driver.find_element(By.XPATH, "//button[@type='submit']").click()
            time.sleep(3)
            totp = driver.find_element(By.XPATH, "//input[@placeholder='••••••']")
            totp_token = TOTP(self.totp)
            print("totp: ", self.totp)
            token = totp_token.now()
            print("totp token: ", token)
            totp.send_keys(token)
            #driver.find_element(By.XPATH, '/html/body/div[1]/div/div[2]/div[1]/div/div/div[2]/form/div[3]/button').click()
            print("before sleep")
            time.sleep(5)
            print("driver.current_url.split: ", driver.current_url)
            request_token = driver.current_url.split('request_token=')[1][:32]
            print("request_token: ", request_token)
            print("end of request token")

        except:
            print("Exception while getting request token")
            traceback.print_exc()

        return request_token

    # p_option_type - CE or PE
    def get_option_name(self, p_symbol: str, p_str_date: str, p_is_month_expiry:bool, p_str_option_price, p_option_type: str):
        lst_split_date = p_str_date.split("-")
        #print(p_symbol, p_str_option_price, p_option_type)
        #print("lst_split_date", lst_split_date[1][0], 0, type(lst_split_date[1][0]))
        #NIFTY25O1425400CE
        if p_is_month_expiry:
            return p_symbol + lst_split_date[2][-2:] + lst_split_date[1].upper() +\
                        p_str_option_price + p_option_type.upper()
        else:
            return p_symbol + lst_split_date[2][-2:] + lst_split_date[1][0].upper() + \
                lst_split_date[0] + p_str_option_price + p_option_type.upper()

    #Historical Data - Start
    def fetchCandleMultipleStocks(self, lst_stocks, str_from_date, str_to_date, interval):
        dict_stock_data = {}
        for stock in lst_stocks:
            data = self.fetchOHLC(stock,str_from_date,str_to_date, interval)
            dict_stock_data[stock] = data
        return dict_stock_data


    def fetchOHLC(self, ticker, str_from_date, str_to_date, interval):
        """extracts historical data and outputs in the form of dataframe"""
        if interval == "1minute":
            interval = "minute"
        retry_number = 1
        data = []
        while retry_number < KITE_API_RETRY_COUNT:
            try:
                instrument = self.__instrumentLookup(ticker)
                kite_data = self.kite.historical_data(instrument,str_from_date, str_to_date,interval)
                data = pd.DataFrame(kite_data)
                lst_candle_type = []
                #add the candle types to list
                for row_index in range(len(data)):
                    candle_type = self.__getCandleType(data.loc[row_index, OPEN_PRICE], data.loc[row_index, CLOSE_PRICE])
                    lst_candle_type.append(candle_type)
                #add candle type column
                data[CANDLE_TYPE] = lst_candle_type
                retry_number = retry_number + 1
                break
            except:
                retry_number = retry_number + 1
                time.sleep(KITE_API_RETRY_TIME)

        return data

    def getTimeFrame(self, str_start_time, str_stop_time, date=dt.date.today()):
        str_from_date = date.strftime("%Y-%m-%d") + " " + str_start_time
        str_to_date = date.strftime("%Y-%m-%d") + " " + str_stop_time
        return str_from_date, str_to_date

    # Historical Data -

    # order info - start
    def getOrderInfo(self, type="symbol"):
        dict_order_data = {}
        retry_number = 1
        while retry_number < KITE_API_RETRY_COUNT:
            try:
                order = self.kite.orders()
                obj_order_data = order_data()
                obj_order_data.stock = order['tradingsymbol']
                obj_order_data.price = order['price']
                obj_order_data.quantity = order['quantity']
                if order['status'] == "COMPLETE":
                    obj_order_data.status = ORDER_STATUS_COMPLETE
                elif order['status'] == "CANCELLED":
                    obj_order_data.status = ORDER_STATUS_CANCELED
                elif order['status'] == "REJECTED":
                    obj_order_data.status = ORDER_STATUS_REJECTED
                else:
                    obj_order_data.status = ORDER_STATUS_OPEN
                obj_order_data.trans_type = order['transaction_type']
                obj_order_data.order_no = order['order_id']

                # set the key based on type
                key = order['tradingsymbol'] if type == 'symbol' else order['order_id']
                if not key in dict_order_data:
                    lst_order_data = []
                    lst_order_data.append(obj_order_data)
                    dict_order_data[key] = lst_order_data
                else:
                    dict_order_data[key].append(obj_order_data)
                return response
            except:
                retry_number = retry_number + 1
                time.sleep(KITE_API_RETRY_TIME)

        return  dict_order_data

    def getOrderInfoByOrderId(self, order_id):

        # place the order
        retry_number = 1
        response = self.kite.order_history(order_id)
        print("Response: ", response)

        data = pd.DataFrame(response)

        print("order info data: ", data['variety'][0])
        status = ""
        #check whether order id complete or not
        status = data["status"].iloc[-1]
        if status == "COMPLETE":
            status = DEFINE_TRADE_COMPLETE
        #check whether order is cancelled or rejected
        elif status == "CANCELLED" or status == "REJECTED" or status == "CANCEL PENDING":
            status = DEFINE_NOT_TRADED
        else:
            status = DEFINE_TRADE_OPEN


        cls_order_info = order_info(stock=data["tradingsymbol"].iloc[-1],
                                    transaction_type=data["transaction_type"].iloc[-1],
                                    price=data["price"].iloc[-1], status=status, variety=data["variety"][0])
        return cls_order_info

    def isSymbolTraded(self, order_info, tradingsymbol, product="MIS"):
        isTraded = False
        lst_orderinfo = []
        for order in order_info:
            if order["tradingsymbol"] == tradingsymbol and order["product"] == product and not order["status"] == "COMPLETE":
                isTraded = True
                obj_order_info = order_info(stock=order["tradingsymbol"], transaction_type=order["transaction_type"], \
                                            price=order["price"], status=order["status"])
                lst_orderinfo.append(obj_order_info)
                break
        return isTraded

    # order info - end
    def get_quote(self, p_get_quote_req:get_quote_request_data, p_exchange="NSE"):
        retry_number = 0
        response = None

        l_stock = p_get_quote_req.symbol
        if not p_get_quote_req.market_type == "":
            if p_get_quote_req.market_type == "EQ":
                l_stock = p_get_quote_req.symbol + "-" + p_get_quote_req.market_type
        else:
            if p_get_quote_req.symbol == "NIFTY":
                l_stock = "NSE:" + p_get_quote_req.symbol + " 50"
            elif p_get_quote_req.symbol == "BANKNIFTY":
                l_stock = "NSE:" + p_get_quote_req.symbol
            else:
                l_stock = "NFO:" + self.__get_option_name(p_get_quote_req.symbol)

        while retry_number < KITE_API_RETRY_COUNT:
            response = self.kite.quote(l_stock)
            #print("response: ", response)
            if not response == None and l_stock in response:
                response = response[l_stock]
                break
            else:
                print("Response is none while getting quote", l_stock)
                retry_number = retry_number + 1
        return response

    def get_quotes(self, p_lst_get_quote_data_req, p_exchange="NSE"):
        dict_quote_data = {}
        for get_quote_req_data in p_lst_get_quote_data_req:
            response = self.get_quote(p_exchange=p_exchange, p_get_quote_req=get_quote_req_data)
            if not response == None:
                obj_quote_data = self.__extract_quote_data(response)
                dict_quote_data[get_quote_req_data.symbol] = obj_quote_data
        return dict_quote_data

    #place order apis - start#
    def place_order(self,
                    tradingsymbol,
                    transaction_type,
                    quantity,
                    product="MIS",
                    order_type="LIMIT",
                    price=None,
                    variety="regular",
                    exchange="NSE",
                    validity="DAY",
                    validity_ttl=None,
                    disclosed_quantity=None,
                    trigger_price=None,
                    iceberg_legs=None,
                    iceberg_quantity=None,
                    auction_number=None,
                    tag=None,
                    market_type="EQ",
                    sl_price=0.0,
                    profit_price=0.0,
                    trail_price=0.0,
                    amo="No"):
        #change transaction type to lower
        order_id = ""
        transaction_type = transaction_type.lower()


        if amo == "Yes":
            variety = "amo"
        if market_type == "":
            exchange = "NFO"
            if not tradingsymbol == "NIFTY":
                tradingsymbol = self.__get_option_name(tradingsymbol)

        print("Kite Place Order for: ", tradingsymbol, exchange, price, trigger_price, variety)
        # for testing
        #variety = "amo"
        if transaction_type == "buy":
            t_type = "BUY"
        elif transaction_type == "sell":
            t_type = "SELL"
        #place the order
        retry_number = 1
        while retry_number <= KITE_API_RETRY_COUNT:
            try:
                order_id = self.kite.place_order(tradingsymbol = tradingsymbol,
                            transaction_type = t_type,
                            quantity = quantity,
                            product=product,
                            order_type=order_type,
                            price=price,
                            variety=variety,
                            exchange=exchange,
                            validity=validity,
                            validity_ttl=validity_ttl,
                            disclosed_quantity=disclosed_quantity,
                            trigger_price=trigger_price,
                            iceberg_legs=iceberg_legs,
                            iceberg_quantity=iceberg_quantity,
                            auction_number=auction_number,
                            tag=tag)
                print("order_id: ", order_id)
                if not order_id == "":
                    break
                else:
                    retry_number = retry_number + 1
                    time.sleep(KITE_API_RETRY_TIME)
            except:
                print("Exception occurred while placing order", order_id)
                #traceback.print_exc()
                retry_number = retry_number + 1
                time.sleep(KITE_API_RETRY_TIME)
        return order_id

    def modify_order(self,
                     order_id,
                     variety="regular",
                     parent_order_id=None,
                     quantity=None,
                     price=None,
                     order_type=None,
                     trigger_price=None,
                     validity=None,
                     disclosed_quantity=None):

        retry_number = 1
        resp_order_id = ""
        #for testing
        #variety = "amo"
        order_info_data: order_info = self.getOrderInfoByOrderId(order_id)
        while retry_number <= KITE_API_RETRY_COUNT:
            try:
                resp_order_id = self.kite.modify_order(
                     variety=order_info_data.variety,
                     order_id=order_id,
                     parent_order_id=parent_order_id,
                     quantity=quantity,
                     price=price,
                     order_type=order_type,
                     trigger_price=trigger_price,
                     validity=validity,
                     disclosed_quantity=disclosed_quantity)

                if not resp_order_id == "":
                    break
                else:
                    retry_number = retry_number + 1
                    time.sleep(KITE_API_RETRY_TIME)
            except:
                print("Exception occurred while modifying order", order_id)
                traceback.print_exc()
                retry_number = retry_number + 1
                time.sleep(KITE_API_RETRY_TIME)
        return resp_order_id

    def cancel_order(self, order_id, variety="regular", parent_order_id=None):
        retry_number = 1
        resp_order_id = ""
        self.kite
        # for testing
        #variety = "amo"
        while retry_number <= KITE_API_RETRY_COUNT:
            try:
                order_info_data:order_info = self.getOrderInfoByOrderId(order_id)
                resp_order_id = self.kite.cancel_order(variety=order_info_data.variety, order_id=order_id, parent_order_id=parent_order_id)
                if not resp_order_id == "":
                    break
                else:
                    retry_number = retry_number + 1
                    time.sleep(KITE_API_RETRY_TIME)
            except:
                print("Exception occurred while cancelling order", order_id)
                traceback.print_exc()
                retry_number = retry_number + 1
                time.sleep(KITE_API_RETRY_TIME)

        return resp_order_id

    def cancel_all_orders(self, product="MIS"):
        order_info = self.getOrderInfo()
        for order in order_info:
            if order["product"] == product and order["status"].find("CANCELLED") < 0:
                print("Candelling order: ", order["order_id"])
                self.cancel_order(order_id = order["order_id"], variety=order["variety"])

    #place order apis - stop
    #private functions
    def __instrumentLookup(self, symbol):
        """Looks up instrument token for a given script from instrument dump"""
        try:
            return self.instrument_df[self.instrument_df.tradingsymbol==symbol].instrument_token.values[0]
        except:
            return -1

    def __getCandleType(self, i_open_price, i_close_price):
        candle_type = "notknown"
        if( i_open_price > i_close_price):
            candle_type = "RED"
        elif(i_open_price < i_close_price):
            candle_type = "GREEN"

        return candle_type


    def __extract_quote_data(self, p_response):
        obj_quote_data = quote_data()
        #open price
        try:
            obj_quote_data.open = float(p_response["ohlc"]["open"])
        except:
            obj_quote_data.open = -1.0

        #high price
        try:
            obj_quote_data.high = float(p_response["ohlc"]["high"])
        except:
            obj_quote_data.high = -1.0

        #low price
        try:
            obj_quote_data.low = float(p_response["ohlc"]["low"])
        except:
            obj_quote_data.low = -1.0

        #close price
        try:
            obj_quote_data.prev_close = float(p_response["ohlc"]["close"])
        except:
            obj_quote_data.prev_close = -1.0

        #close price
        try:
            obj_quote_data.ltp = float(p_response["last_price"])
        except:
            obj_quote_data.ltp = -1.0

        #volume
        try:
            obj_quote_data.volume = float(p_response["volume"])
        except:
            obj_quote_data.volume = -1.0

        return obj_quote_data

    def __get_option_name(self, p_symbol: str):
        is_monthly_expiry_date = is_monthly_expiry(p_symbol)
        index_type, expiry_date, option_price, option_type = self.__get_option_name_details(p_symbol)
        if is_monthly_expiry_date:
            #print("it is monthly expiry", option_price)
            #print((index_type + expiry_date.split("-")[2] + expiry_date.split("-")[1] + option_price + option_type))
            return index_type + expiry_date.split("-")[2] + expiry_date.split("-")[1] + option_price + option_type
        else:
            return index_type + expiry_date.split("-")[2] + expiry_date.split("-")[1][0:1] + expiry_date.split("-")[0] + \
                option_price + option_type

    def __get_option_name_details(self, p_strInput: str):
        digit_position = get_position_of_first_digit(p_strInput)
        index_type = p_strInput[:digit_position]
        expiry_date = p_strInput[digit_position:(digit_position + 2)] \
                      + "-" + p_strInput[(digit_position + 2):(digit_position + 5)] \
                      + "-" + p_strInput[(digit_position + 5):(digit_position + 7)]
        option_price = p_strInput[(digit_position + 7):(digit_position + 12)]
        option_type = p_strInput[(digit_position + 12):(digit_position + 14)]
        print(p_strInput[(digit_position + 7):(digit_position + 12)])
        print(index_type, expiry_date, option_price, option_type)
        return index_type, expiry_date, option_price, option_type
