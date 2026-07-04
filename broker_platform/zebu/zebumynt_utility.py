# -*- coding: utf-8 -*-
"""
Zerodha Kite Connect - Historical Data

"""

from myntapi import app
import logging
import os
import datetime as dt
import pandas as pd
import traceback
import pyotp
from DataTypes.defines import *
from DataTypes.trade_data import *
import time
#import datetime
from datetime import datetime
from datetime import timedelta
import json


# Define
ZEBYMYNT_API_RETRY_COUNT = 8
ZEBYMYNT_API_RELOGIN_COUNT = 3
ZEBYMYNT_API_RETRY_TIME = 2
ZEBYMYNT_INVALID_SYMBOL_ERROR = 'Please provide a valid symbol'


class zebumynt_utitlity:
    def __init__(self, user_name, client_id, secret_id, pin, totp, phone_no, refresh_token=""):
        #refresh token not required, but decleared to have unique method parameters
        # generate trading session
        self.dict_token = {}
        try:
            self.is_running = False
            self.logs_path = os.getcwd() + "/Logs/"
            self.user_name = ' '.join(user_name.split())
            #self.app_id = ' '.join(client_id.split())
            self.secret_id = ' '.join(secret_id.split())
            self.pin = ' '.join(pin.split())
            self.totp = ' '.join(str(totp).split())
            self.phone_no = ' '.join(phone_no.split())
            self.redirect_url = "http://google.com/"
            self.response_type = "code"
            self.state = "sample_state"
            self.dict_token['NIFTYBANK-INDEX'] = "26009"
            self.dict_token['NIFTY50-INDEX'] = "26000"
            self.dict_token['INDIAVIX-INDEX'] = "26017"
            self.login()

        except:
            print("Exception in zebumynt utility constructor")
            print(traceback.print_exc())

    def login(self, is_re_login = False):
        self.zebumynt = app()
        print("Before Logging in", self.user_name, self.pin, self.totp, self.secret_id, self.phone_no)
        ret = self.zebumynt.login(userid=self.user_name, password=self.pin, twoFA=self.totp, vendor_code=self.user_name,
                                  api_secret=self.secret_id, imei=self.phone_no)
        print("ret: ", ret)
        self.susertoken = ret["susertoken"]
        self.is_running = True

    def get_running_status(self):
        return self.is_running

    # Historical Data - Start
    def fetchCandleMultipleStocks(self, lst_stocks, str_from_date,
                                  str_to_date, interval, all_data=False,
                                  exchange="NSE", market_type="EQ", lst_market_type=None):
        dict_stock_data = {}
        i_market_type_index = 0
        for stock in lst_stocks:
            # if the list of market type is provided then use from list or use market type
            market_type = ""
            if not lst_market_type == None:
                market_type = lst_market_type[i_market_type_index]
                i_market_type_index = i_market_type_index + 1
            data = self.fetchOHLC(ticker=stock,str_from_date=str_from_date,
                                 str_to_date=str_to_date, interval=interval,
                                 all_data=all_data, exchange=exchange, market_type=market_type)
            if CANDLE_TYPE in data:
                dict_stock_data[stock] = data
            time.sleep(1 / 3)
        return dict_stock_data

    def fetchOHLC(self, ticker, str_from_date, str_to_date, interval, all_data=False, exchange="NSE", market_type="EQ"):
        """extracts historical data and outputs in the form of dataframe"""
        #replace minute or second or hour
        data = []
        retry_number = 0
        response = ""
        #print("market_type: ", market_type)
        if not market_type == "":
            if market_type == "EQ":
                ticker = ticker + "-" + market_type
        else:
            ticker = self.__get_option_name(ticker)

        exchange, ticker = self.get_updated_exchange_token(ticker)
        interval = interval.lower()
        while retry_number < ZEBYMYNT_API_RETRY_COUNT:
            try:
                if "minute" in interval:
                    i_interval = int(interval.replace("minute", ""))
                    response = self.zebumynt.get_time_price_series(exchange=exchange, token = ticker,\
                                                    starttime=str_from_date, endtime=str_to_date,\
                                                    interval=int(i_interval))
                    #print("response2", response)
                else:
                    i_interval = 60
                    #response = self.zebumynt.get_time_price_series(exchange=exchange, token=ticker, \
                    #                                               starttime=str_from_date, endtime=str_to_date, \
                    #                                               interval=int(i_interval))
                    response = self.zebumynt.get_daily_price_series(exchange=exchange, tradingsymbol=ticker, \
                                                                     startdate=str_from_date, enddate=str_to_date)
                    print("response1: ", ticker, response, exchange)

                    # # Convert to a Python dictionary
                    data_dict = json.loads(response[0])
                    response.clear()
                    response = [data_dict]
                #print("response: ", response, ticker, str_from_date, str_to_date)
                if not response == None:
                    if ("day" in interval or response[0]['stat'] == 'Ok'):
                        response = response[::-1]
                        data = pd.DataFrame.from_dict(response)
                        data.rename(columns={'time': DATE_TIME, 'into': OPEN_PRICE, 'inth': HIGH_PRICE,
                                             'intl': LOW_PRICE, 'intc': CLOSE_PRICE, 'intv': VOLUME_DATA,
                                             'intvwap': VWAP}, inplace=True)
                        #print("data: ", data)

                        if "day" in interval:
                            dict_day = {DATE_TIME: data[DATE_TIME][0], OPEN_PRICE:data[OPEN_PRICE][0], HIGH_PRICE:data[HIGH_PRICE][0],
                                        LOW_PRICE: data[LOW_PRICE][0], CLOSE_PRICE:data[CLOSE_PRICE][0], VOLUME_DATA:data[VOLUME_DATA][0],
                                        VWAP: 0.0}
                            data = pd.DataFrame([dict_day])
                        else:
                            data[VWAP] = data[VWAP].astype(float)

                        #add the candle type
                        lst_candle_type = []
                        for row_index in range(len(data)):
                            candle_type = self.__getCandleType(float(data.loc[row_index, OPEN_PRICE]),
                                                               float(data.loc[row_index, CLOSE_PRICE]))
                            lst_candle_type.append(candle_type)

                        # add candle type column
                        data[CANDLE_TYPE] = lst_candle_type
                        #change to float data type
                        data[OPEN_PRICE] = data[OPEN_PRICE].astype(float)
                        data[HIGH_PRICE] = data[HIGH_PRICE].astype(float)
                        data[LOW_PRICE] = data[LOW_PRICE].astype(float)
                        data[CLOSE_PRICE] = data[CLOSE_PRICE].astype(float)
                        data[VOLUME_DATA] = data[VOLUME_DATA].astype(float)
                        break
                else:
                    retry_number = retry_number + 1
            except:
                print("Exceptiion while reading historic data in Zebu", ticker)
                print(traceback.print_exc())
                retry_number = retry_number + 1
                time.sleep(2)
            '''
            #check whether relogin is requires
            if retry_number >= ZEBYMYNT_API_RELOGIN_COUNT:
                print("Performing ZebuMynt Re-login")
                time.sleep(5)
                self.login(True)
                time.sleep(2)
            '''
        return data


    # Historical Data - END

    def getTimeFrame(self, str_start_time="05:30:00", str_stop_time="05:30:00", date=dt.date.today(), p_no_of_days = 0):
        str_from_date = date.strftime("%Y-%m-%d") + " " + str_start_time
        str_from_date = datetime.strptime(str_from_date, '%Y-%m-%d %H:%M:%S').strftime('%s')
        str_to_date = date.strftime("%Y-%m-%d") + " " + str_stop_time
        str_to_date = datetime.strptime(str_to_date, '%Y-%m-%d %H:%M:%S').strftime('%s')
        return str_from_date, str_to_date

    def getTimeFrameMultiDays(self, str_start_time="05:30:00", str_stop_time="05:30:00", date=dt.date.today(), p_no_of_days=0, p_end_date=0):
        start_date = date - timedelta(p_no_of_days)
        print("start_date", start_date)
        str_from_date = start_date.strftime("%Y-%m-%d") + " " + str_start_time
        str_from_date = datetime.strptime(str_from_date, '%Y-%m-%d %H:%M:%S').strftime('%s')
        end_date = date - timedelta(p_end_date)
        str_to_date = end_date.strftime("%Y-%m-%d") + " " + str_stop_time
        str_to_date = datetime.strptime(str_to_date, '%Y-%m-%d %H:%M:%S').strftime('%s')
        return str_from_date, str_to_date

    # place order apis - start#
    def place_order(self,
                    tradingsymbol,
                    transaction_type,
                    quantity,
                    product="MIS",
                    order_type="LIMIT",
                    price=0,
                    variety="regular",
                    exchange="NSE",
                    validity="DAY",
                    validity_ttl=None,
                    disclosed_quantity=0,
                    trigger_price=0,
                    iceberg_legs=None,
                    iceberg_quantity=None,
                    auction_number=None,
                    tag=None,
                    market_type="EQ",
                    sl_price=0.0,
                    profit_price=0.0,
                    trail_price=0.0,
                    amo="No"):
        # for testing
        # variety = "amo"

        print("Placing Order: ", tradingsymbol, transaction_type, market_type, amo)

        #set exchange
        exchange = "NSE" if market_type == "EQ" else "NFO"

        #update trading symbol
        if not market_type == "":
            if market_type == "EQ":
                tradingsymbol = tradingsymbol + "-" + market_type
        else:
            tradingsymbol = self.__get_option_name(tradingsymbol)

        #modify transaction type
        transaction_type = transaction_type.lower()
        if transaction_type == "buy":
            transaction_type = "B"
        elif transaction_type == "sell":
            transaction_type = "S"

        #set the product
        l_delivery_type = "C" if market_type == "EQ" else "M"
        dict_product_type = {"CNC": l_delivery_type, "MIS": "I", "CO": "H", "BO": "B"}
        if product in dict_product_type.keys():
            product = dict_product_type[product]
        else:
            product = "MIS"

        #set the order type
        dict_order_type = {"LIMIT": "LMT", "MARKET": "MKT", "SL-M": "SL-MKT", "SL": "SL-LMT"}
        if order_type in dict_order_type.keys():
            order_type = dict_order_type[order_type]
        else:
            order_type = "LMT"

        #set the validity
        dict_validity_type = {"DAY": "DAY", "EOS": "EOS", "IOC": "IOC"}
        if validity in dict_validity_type.keys():
            validity = dict_validity_type[validity]
        else:
            validity = "DAY"

        #place order
        retry_number = 0
        while retry_number < ZEBYMYNT_API_RETRY_COUNT:
            disclosed_quantity = 0
            print("Request Data: ", transaction_type, tradingsymbol, product, exchange,
                quantity, disclosed_quantity, order_type, price, trigger_price, validity,
                  amo)
            response = self.zebumynt.place_order(buy_or_sell=transaction_type, tradingsymbol=tradingsymbol,\
                                                 product_type=product, exchange=exchange, quantity=quantity,\
                                                 discloseqty=disclosed_quantity, price_type=order_type,\
                                                 price=price,trigger_price=trigger_price,retention=validity,\
                                                 remarks="algo trading",bookloss_price=sl_price,\
                                                 bookprofit_price=profit_price, trail_price=trail_price,amo=amo)
            order_id = ""
            if not response == None:
                if response['stat'] == "Ok":
                    order_id = response['norenordno']
                    break
            else:
                print("Response is None - Placing Order")
                retry_number = retry_number + 1
                time.sleep(ZEBYMYNT_API_RETRY_TIME)

        return order_id

    def modify_order(self,
                     order_id,
                     variety="regular",
                     parent_order_id=None,
                     quantity=0,
                     price=0.0,
                     order_type="LIMIT",
                     trigger_price=0.0,
                     validity=None,
                     disclosed_quantity=None,
                     tradingsymbol="",
                     market_type="",
                     exchange="NSE",
                     sl_price=0.0,
                     profit_price=0.0,
                     trail_price=0.0):
        # for testing
        # variety = "amo"
        print(__name__)

        if not order_id == "":
            # set exchange
            exchange = "NSE" if market_type == "EQ" else "NFO"

            # update trading symbol
            if not tradingsymbol == "":
                if not market_type == "":
                    tradingsymbol = tradingsymbol + "-" + market_type
                else:
                    tradingsymbol = self.__get_option_name(tradingsymbol)

            # set the order type
            dict_order_type = {"LIMIT": "LMT", "MARKET": "MKT", "SL-M": "SL-MKT", "SL": "SL-LMT"}
            if order_type in dict_order_type.keys():
                order_type = dict_order_type[order_type]
            else:
                order_type = ""

            dict_args = {"exchange":"exchange", "tradingsymbol":"tradingsymbol", "orderno":order_id}
            if not order_type == "":
                dict_args["newprice_type"] = "order_type"

            #set the quantity
            if quantity > 0:
                dict_args["newquantity"] = "quantity"

            #set price
            if price > 0.0:
                dict_args["newprice"] = "price"
            #set trigger price
            if trigger_price > 0.0:
                dict_args["newtrigger_price"] = "trigger_price"
            #set book loss price
            if sl_price > 0.0:
                dict_args["bookloss_price"] = "sl_price"
            #set profit price
            if profit_price > 0.0:
                dict_args["bpprc"] = "profit_price"
            #set trail price
            if trail_price > 0.0:
                dict_args["blprc"] = "trail_price"
            #construct the argument string
            l_args = ""
            for key, value in dict_args.items():
                if l_args == "":
                    l_args = key + "=" + str(value)
                else:
                    l_args = l_args + ", " + key + "=" + str(value)
            #construct function call instruction
            print("l_args: ", l_args)
            str_code = "self.zebumynt.modify_order(" + l_args + ")"
            retry_number = 0
            print(str_code)
            while retry_number < ZEBYMYNT_API_RETRY_COUNT:
                response = eval(str_code)
                print("response: ", response)
                if not response == None and response['stat'] == "Ok":
                    order_id = response['result']
                    break
                else:
                    retry_number = retry_number + 1
        return order_id

    def cancel_order(self, order_id, variety="regular", parent_order_id=None):
        print("Cancelling Order: ", order_id)
        retry_number = 0
        while retry_number < ZEBYMYNT_API_RETRY_COUNT:
            response = self.zebumynt.cancel_order(orderno=order_id)
            if not response == None:
                break
            else:
                retry_number = retry_number + 1
        return response

    def get_quote(self, p_get_quote_req:get_quote_request_data, p_exchange="NSE"):
        retry_number = 0
        response = None
        l_stock = p_get_quote_req.symbol
        if not p_get_quote_req.market_type == "":
            if p_get_quote_req.market_type == "EQ":
                l_stock = p_get_quote_req.symbol + "-" + p_get_quote_req.market_type
        else:
            l_stock = self.__get_option_name(p_get_quote_req.symbol)

        p_exchange, l_stock = self.get_updated_exchange_token(l_stock)

        while retry_number < ZEBYMYNT_API_RETRY_COUNT:
            response = self.zebumynt.get_quotes(exchange=p_exchange, token=l_stock)
            if not response == None:
                break
            else:
                print("Response is none while getting quote", l_stock)
                retry_number = retry_number + 1
        return response

    def get_future_name(self, symbol:str, expiry_date:str):
        split_data = expiry_date.split("-")
        return f"{symbol}{split_data[0]}{split_data[1]}{split_data[2][-2:]}F"

    def get_quotes(self, p_lst_get_quote_data_req, p_exchange="NSE"):
        dict_quote_data = {}
        for get_quote_req_data in p_lst_get_quote_data_req:
            response = self.get_quote(p_exchange=p_exchange, p_get_quote_req=get_quote_req_data)
            if not response == None:
                obj_quote_data = self.__extract_quote_data(response)
                dict_quote_data[get_quote_req_data.symbol] = obj_quote_data

        return dict_quote_data

    # order info - start
    # order info - start
    #type - symbol or orderid
    def getOrderInfo(self, type="symbol"):
        retry_number = 1
        dict_order_data = {}
        while retry_number < ZEBYMYNT_API_RETRY_COUNT:
            response = self.zebumynt.get_order_book()
            if not response == None:

                for order in response:
                    try:
                        obj_order_data = order_data()
                        obj_order_data.stock = order['tsym']
                        obj_order_data.price = order['prc']
                        obj_order_data.quantity = order['qty']
                        obj_order_data.status = order['status']
                        obj_order_data.trans_type = order['trantype']
                        obj_order_data.order_no = order['norenordno']
                    except:
                        pass
                    #set the key based on type
                    key = order['tsym'] if type == 'symbol' else order['norenordno']
                    if not key in dict_order_data:
                        lst_order_data = []
                        lst_order_data.append(obj_order_data)
                        dict_order_data[key] = lst_order_data
                    else:
                        dict_order_data[key].append(obj_order_data)
                break
            else:
                retry_number = retry_number + 1
                time.sleep(ZEBYMYNT_API_RETRY_TIME)
        return dict_order_data

    def getOrderInfoByOrderId(self, order_id):
        print(__name__)
        retry_number = 1
        obj_order_data = order_data()
        while retry_number < ZEBYMYNT_API_RETRY_COUNT:
            response = self.zebumynt.single_order_history(orderno=order_id)
            if not response == None:
                obj_order_data.order_no = response[0]['norenordno']
                obj_order_data.status = response[0]['status']
                obj_order_data.price = response[0]['prc']
                obj_order_data.quantity = response[0]['qty']
                obj_order_data.trans_type = response[0]['tsym'].replace("-EQ","")
                break
            else:
                retry_number = retry_number + 1
                time.sleep(ZEBYMYNT_API_RETRY_TIME)

        return obj_order_data


    # p_option_type - CE or PE
    def get_option_name(self, p_symbol: str, p_str_date: str, p_is_month_expiry:bool, p_str_option_price, p_option_type: str):
        lst_split_date = p_str_date.split("-")
        #BANKNIFTY16APR24P47400
        return p_symbol + lst_split_date[0] + lst_split_date[1].upper() +\
               lst_split_date[2][-2:] + p_option_type[0].upper() + p_str_option_price

    def get_updated_exchange_token(self, p_strstock):
        lst_index = ["NIFTYBANK-INDEX", "NIFTY50-INDEX", "INDIAVIX-INDEX"]
        l_exchange = "NSE" if "EQ" in p_strstock or (p_strstock in lst_index) else "NFO"
        l_token = p_strstock
        if p_strstock in self.dict_token:
            l_token = self.dict_token[p_strstock]
        return l_exchange, l_token


# Private Function  -Start
    def __extract_quote_data(self, p_response):
        obj_quote_data = quote_data()

        #open price
        try:
            obj_quote_data.open = float(p_response['o'])
        except:
            try:
                obj_quote_data.open = float(p_response['lp'])
            except:
                obj_quote_data.open = -1.0

        #high price
        try:
            obj_quote_data.high = float(p_response['h'])
        except:
            obj_quote_data.high = -1.0

        #low price
        try:
            obj_quote_data.low = float(p_response['l'])
        except:
            obj_quote_data.low = -1.0

        #close price
        try:
            obj_quote_data.prev_close = float(p_response['c'])
        except:
            obj_quote_data.prev_close = -1.0

        #close price
        try:
            obj_quote_data.ltp = float(p_response['lp'])
        except:
            obj_quote_data.ltp = -1.0

        #volume
        try:
            obj_quote_data.volume = float(p_response['v'])
        except:
            obj_quote_data.volume = -1.0

        return obj_quote_data

    def get_option_chain(self):
        print(self.zebumynt.get_option_chain(exchange="NFO", tradingsymbol="NIFTY10MAR26P24500", strikeprice="24500"))

    def search_scrip(self, searchtext, exchange="NSE"):
        ret = self.zebumynt.searchscrip(exchange=exchange, searchtext=searchtext)
        print(ret)

    # --------------PRIVATE METHODS START----------------------------------------

    def __getCandleType(self, i_open_price, i_close_price):
        candle_type = "notknown"
        if (i_open_price > i_close_price):
            candle_type = "RED"
        elif (i_open_price < i_close_price):
            candle_type = "GREEN"

        return candle_type

    def __get_option_name(self, p_strInput: str):
        index_type, expiry_date, option_price, option_type = get_option_name_details(p_strInput)
        return index_type + expiry_date[0:2] + expiry_date[3:6] + expiry_date[7:9] + option_type[
            0].upper() + option_price


    # --------------PRIVATE METHODS END----------------------------------------

