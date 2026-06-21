# -*- coding: utf-8 -*-
"""
Fyers utility
"""

#from fyers_apiv3 import accessToken
try:
    from fyers_apiv3 import fyersModel
except ImportError:
    class _MissingFyersModel:
        class FyersModel:
            def __init__(self, *args, **kwargs):
                raise ImportError("Install fyers-apiv3 to use live FYERS sessions.")

        class SessionModel:
            def __init__(self, *args, **kwargs):
                raise ImportError("Install fyers-apiv3 to use live FYERS sessions.")

    fyersModel = _MissingFyersModel
import os
import traceback
#from utility import *
try:
    import pyotp
except ImportError:
    class _MissingPyotp:
        class TOTP:
            def __init__(self, *args, **kwargs):
                raise ImportError("Install pyotp to use FYERS TOTP login flows.")

    pyotp = _MissingPyotp
from datetime import *
import calendar
import webbrowser
import time
from datatypes.defines import *
from datatypes.trade_data import get_quote_request_data, quote_data
from broker_platform.fyers.fyers_auth import is_token_expired, refresh_access_token
import datetime as dt
import yaml
from yaml import SafeLoader
try:
    import pandas as pd
except ImportError:
    pd = None

#Define
FYERS_API_RETRY_COUNT = 5
FYERS_API_RETRY_TIME = 1
FYERS_INVALID_SYMBOL_ERROR = 'Please provide a valid symbol'


class fyers_session_model:
    def __init__(self, config_file):

        #get the config file data
        self.config_file = config_file
        with open(self.config_file) as utility_data:
            self.utility_data = yaml.load(utility_data, Loader=SafeLoader)

        #generate trading session
        #self.config = config()
        #self.utility = utitlity()
        self.logs_path = os.getcwd() + "/Logs/"
        self.user_name = self.utility_data["user_name"]
        self.app_id = self.utility_data["client_id"]
        self.secret_id = self.utility_data["secret_id"]
        self.pin = str(self.utility_data["pin"])
        self.totp = self.utility_data["totp"]
        self.phone_no = self.utility_data["phone_no"]

        totp = pyotp.TOTP(self.totp)
        print("Use this TOTP for login in Web Browser: ", totp.now())

    def get_tokens(self):
        try:
            appSession = fyersModel.SessionModel(client_id=self.app_id,
                                                  secret_key=self.secret_id,
                                                  redirect_uri="http://google.com/",
                                                  response_type="code",
                                                  grant_type="authorization_code")
            tokenURL = appSession.generate_authcode()
            #print("tokenURL: ", tokenURL)
            # This command is used to open the url in default system brower
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            webbrowser.register('chrome', None, webbrowser.BackgroundBrowser(chrome_path))
            obj_web_browser = webbrowser.get('chrome')
            obj_web_browser.open_new_tab(tokenURL)
            authUrl = input('Enter the URL from redirect URL')
            appSession.set_token(authUrl.split('auth_code=')[1].split('&state')[0])
            generate_token = appSession.generate_token()
            self.utility_data['zaccess_token'] = generate_token['access_token']
            self.utility_data['zrefresh_token'] = generate_token['refresh_token']
            #print(self.utility_data['zrefresh_token'])
            with open(self.config_file, 'w') as fp:
                yaml.dump(self.utility_data, fp)
        except:
            traceback.print_exc()

class fyers_utitlity:
    def __init__(self, user_name, client_id, secret_id, pin, totp, phone_no, refresh_token="", access_token=""):
        #generate trading session
        try:
            self.is_running = False
            self.logs_path = os.getcwd() + "/Logs/"
            os.makedirs(self.logs_path, exist_ok=True)
            self.user_name = user_name
            self.app_id = client_id
            self.secret_id = secret_id
            self.pin = str(pin)
            self.totp = totp
            self.phone_no = phone_no
            self.redirect_url = "http://google.com/"
            self.response_type = "code"
            self.state = "sample_state"
            self.refresh_token = refresh_token
            access_token_expired = is_token_expired(access_token) if access_token else False
            if access_token and not access_token_expired:
                self.access_token = access_token
            else:
                try:
                    if access_token_expired:
                        print("FYERS access token is expired; attempting refresh-token authentication.")
                    if self.refresh_token:
                        self.access_token = self.__get_access_token_by_refresh_token()
                    else:
                        raise RuntimeError("No refresh token configured.")
                except Exception as exc:
                    print("FYERS refresh-token authentication failed:", exc)
                    print("Falling back to manual auth-code login. Open the FYERS URL and paste the redirect URL/auth-code back here.")
                    self.access_token = self.__getAccessToken()
            self.fyers = fyersModel.FyersModel(client_id=self.app_id, token=self.access_token,log_path=self.logs_path)
            self.is_running = True
            time.sleep(5)
        except Exception as exc:
            print(f"Exception in fyers utility constructor: {exc}")
            raise

    def get_running_status(self):
        return self.is_running

    def __is_token_expired(self, token):
        return is_token_expired(token)

    def __get_access_token_by_refresh_token(self):
        access_token = refresh_access_token(
            client_id=self.app_id,
            secret_key=self.secret_id,
            pin=self.pin,
            refresh_token=self.refresh_token,
        )
        self.is_running = True
        return access_token

    def __getAccessToken(self):
        try:
            appSession = fyersModel.SessionModel(client_id=self.app_id,
                                                  secret_key=self.secret_id,
                                                  redirect_uri="http://google.com/",
                                                  response_type="code",
                                                  grant_type="authorization_code")
            tokenURL = appSession.generate_authcode()
            print("Open this FYERS auth URL in your browser to generate a fresh access token:")
            print(tokenURL)
            try:
                webbrowser.open(tokenURL)
            except Exception:
                pass
            time.sleep(1)
            authUrl = self.__get_url_token_manual(tokenURL)
            appSession.set_token(authUrl)
            generate_token = appSession.generate_token()
            print("Generate Token status - ", generate_token.get("s", "unknown"))
            return generate_token['access_token']
        except:
            traceback.print_exc()

    def __get_url_token_manual(self, str_url):
        print("Token Url: ", str_url)
        authUrl = input('Paste the full redirect URL (or auth_code) from FYERS here: ').strip()
        if 'auth_code=' in authUrl:
            return authUrl.split('auth_code=')[1].split('&state')[0]
        if 'code=' in authUrl:
            return authUrl.split('code=')[1].split('&state')[0]
        return authUrl

    def __get_url_token(self, str_url):
        from selenium import webdriver
        from selenium.webdriver.common.by import By

        driver = webdriver.Chrome()
        driver.get(str_url)
        try:
            username = driver.find_element(By.XPATH, "//input[@id='mobile-code']")
            for data in str(self.phone_no):
                username.send_keys(data)
            time.sleep(2)
            driver.find_element(By.XPATH, "//button[@id='mobileNumberSubmit']").click()
        except:
            username = driver.find_element(By.XPATH, "//input[@id='fy_client_id']")
            username.send_keys(self.user_name)
            driver.find_element(By.XPATH, "//button[@id='clientIdSubmit']").click()

        time.sleep(30)
        totp = pyotp.TOTP(self.totp)
        time.sleep(3)
        driver.find_element(By.XPATH, "//input[@id='first']").send_keys(totp.now()[0])
        driver.find_element(By.XPATH, "//input[@id='second']").send_keys(totp.now()[1])
        driver.find_element(By.XPATH, "//input[@id='third']").send_keys(totp.now()[2])
        driver.find_element(By.XPATH, "//input[@id='fourth']").send_keys(totp.now()[3])
        driver.find_element(By.XPATH, "//input[@id='fifth']").send_keys(totp.now()[4])
        driver.find_element(By.XPATH, "//input[@id='sixth']").send_keys(totp.now()[5])
        driver.find_element(By.XPATH, "//button[@id='confirmOtpSubmit']").click()
        time.sleep(3)
        driver.find_element(By.ID, "verify-pin-page").find_element(By.ID, "first").send_keys(self.pin[0])
        driver.find_element(By.ID, "verify-pin-page").find_element(By.ID, "second").send_keys(self.pin[1])
        driver.find_element(By.ID, "verify-pin-page").find_element(By.ID, "third").send_keys(self.pin[2])
        driver.find_element(By.ID, "verify-pin-page").find_element(By.ID, "fourth").send_keys(self.pin[3])
        driver.find_element(By.XPATH, "//button[@id='verifyPinSubmit']").click()
        time.sleep(3)
        return driver.current_url.split('auth_code=')[1].split('&state')[0]

    def __getCandleType(self, i_open_price, i_close_price):
        candle_type = "notknown"
        if (i_open_price > i_close_price):
            candle_type = "RED"
        elif (i_open_price < i_close_price):
            candle_type = "GREEN"

        return candle_type

    def __format_fyers_symbol(self, symbol, exchange="NSE", market_type="EQ"):
        """Return FYERS v3 symbol format, accepting either base or full symbols."""
        formatted = symbol if ":" in symbol else f"{exchange}:{symbol}"
        if market_type and not formatted.endswith(f"-{market_type}"):
            formatted = f"{formatted}-{market_type}"
        if not market_type and (formatted.endswith("CE-INDEX") or formatted.endswith("PE-INDEX")):
            formatted = formatted.replace("-INDEX", "")
        return formatted

    def __quote_key_aliases(self, full_symbol, request_symbol, market_type):
        aliases = {full_symbol, request_symbol}
        base = full_symbol.split(":", 1)[-1]
        aliases.add(base)
        if market_type and base.endswith(f"-{market_type}"):
            aliases.add(base[: -(len(market_type) + 1)])
        return aliases
    # --------------PRIVATE METHODS END----------------------------------------

    #p_option_type - CE or PE
    def get_option_name(self, p_symbol:str, p_str_date:str, p_is_month_expiry, p_str_option_price, p_option_type:str):
        print(p_symbol, p_str_date)
        l_str_option_format = self.convert_expiry_date_to_option_format(p_str_date, p_is_month_expiry)
        return p_symbol + l_str_option_format + p_str_option_price + p_option_type


    def convert_expiry_date_to_option_format(self, p_strdate, is_month_expiry):
        l_str_option_name = ""
        l_str_date = ""
        lst_split_date = p_strdate.split("-")
        l_str_year = lst_split_date[2]
        # get last two digits from year
        l_str_year = l_str_year[len(l_str_year) - 2:]
        l_str_month = lst_split_date[1]


        if l_str_month.isdigit() == False:
            l_str_month = str(list(calendar.month_abbr).index(l_str_month))

        # if month is less than 10 then remove 0
        if int(l_str_month) < 10:
            l_str_month = l_str_month.replace("0", "")
        # if the date is month expiry then convert month to 3 letters (Ex: MAR) format
        if is_month_expiry:
            Months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
            l_str_month = Months[int(l_str_month) - 1]
        else:
            Months = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "1O", "11", "12"]
            l_str_month = Months[int(l_str_month) - 1]
            l_str_date = lst_split_date[0]


        return (l_str_year + l_str_month + l_str_date)

    #Historical Data - Start
    def fetchCandleMultipleStocks(self, lst_stocks, str_from_date,
                                  str_to_date, interval, all_data=False,
                                  exchange="NSE", market_type="EQ",lst_market_type = None):
        dict_stock_data = {}
        i_market_type_index = 0
        print("List of stocks: ", lst_stocks)
        for stock in lst_stocks:
            #if the list of market type is provided then use from list or use market type
            if not lst_market_type == None:
                market_type =lst_market_type[i_market_type_index]
                i_market_type_index = i_market_type_index + 1
            data = self.fetchOHLC(ticker=stock,str_from_date=str_from_date,
                                  str_to_date=str_to_date, interval=interval,
                                  all_data=all_data, exchange=exchange, market_type=market_type)
            if CANDLE_TYPE in data:
                dict_stock_data[stock] = data
            time.sleep(1)
        return dict_stock_data


    def fetchOHLC(self, ticker, str_from_date, str_to_date, interval, all_data=False, exchange="NSE", market_type="EQ"):
        """extracts historical data and outputs in the form of dataframe"""

        # FYERS expects NSE equity symbols in the form NSE:SYMBOL-EQ.
        ticker = "NIFTY" if ticker == "NIFTY50" else ticker
        ticker = self.__format_fyers_symbol(ticker, exchange=exchange, market_type=market_type)


        #modify the interval
        interval = interval.lower()
        #for hour remove hour and multiply by 60
        interval = interval.lower()
        if interval.find("hour") > 0:
            interval = interval.replace("hour", "")
            interval = str(int(interval) * 60)
        elif interval.find("day") > 0:
            interval = "1D"
        elif interval.find("week") > 0:
            interval = "1W"
        else:
            interval = interval.replace("minute", "")

        #modify start and end date
        str_start_date = str_from_date
        str_from_date = str_from_date.split(" ")[0]
        str_to_date = str_to_date.split(" ")[0]

        retry_number = 1
        data = pd.DataFrame()
        response = None
        dict_request = {"symbol": ticker, "resolution": interval, "date_format": "1", "range_from": str_from_date,
                        "range_to": str_to_date, "cont_flag": "1"}
        while retry_number < FYERS_API_RETRY_COUNT:
            try:
                response = self.fyers.history(dict_request)
                #print("Response: ", response)
                historic_data_col = [DATE_TIME, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE,VOLUME_DATA]
                if response.get('s') == 'ok':
                    data = pd.DataFrame.from_dict(response['candles'])
                    data.columns = historic_data_col
                    data[DATE_TIME] = pd.to_datetime(data[DATE_TIME],unit = "s")
                    data[DATE_TIME] = data[DATE_TIME].dt.tz_localize('utc').dt.tz_convert('Asia/Kolkata')
                    data[DATE_TIME] = data[DATE_TIME].dt.tz_localize(None)

                    #change numpy float to float
                    data[OPEN_PRICE] = data[OPEN_PRICE].astype(float)
                    data[HIGH_PRICE] = data[HIGH_PRICE].astype(float)
                    data[LOW_PRICE] = data[LOW_PRICE].astype(float)
                    data[CLOSE_PRICE] = data[CLOSE_PRICE].astype(float)

                    # add the candle types to list
                    lst_candle_type = []
                    for row_index in range(len(data)):
                        candle_type = self.__getCandleType(data.loc[row_index, OPEN_PRICE],
                                                           data.loc[row_index, CLOSE_PRICE])
                        lst_candle_type.append(candle_type)
                    # add candle type column
                    data[CANDLE_TYPE] = lst_candle_type
                    break
                else:
                    print("FYERS history error: ", response.get("code"), response.get("message"))
                    time.sleep(2)
                    data = pd.DataFrame()

                if all_data == False:
                    data = data.loc[data[DATE_TIME] == str_start_date]

                #add candle type column
                retry_number = retry_number + 1
            except:
                print("dict_request: ", dict_request)
                print("Response: ", response)
                traceback.print_exc()
                retry_number = retry_number + 1
                time.sleep(FYERS_API_RETRY_TIME)
        return data

    # Historical Data - END

    def getTimeFrame(self, str_start_time="05:30:00", str_stop_time="05:30:00", start_date=dt.date.today(), stop_date=dt.date.today()):
        str_from_date = start_date.strftime("%Y-%m-%d") + " " + str_start_time
        str_to_date = stop_date.strftime("%Y-%m-%d") + " " + str_stop_time
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
                    sl_price = 0,
                    profit_price=0,
                    trail_price=0.0,
                    amo="No"):
        # for testing
        #variety = "amo"

        # change transaction type to lower
        order_id = ""
        transaction_type = transaction_type.lower()

        #Modify Trading Symbol
        if not market_type == "":
            tradingsymbol = exchange + ":" + tradingsymbol + "-" + market_type
        else:
            tradingsymbol = exchange + ":" + tradingsymbol

        #modify transaction type
        if transaction_type == "buy":
            t_type = 1
        elif transaction_type == "sell":
            t_type = -1

        #Modify the product
        dict_product_type = {"MIS": "INTRADAY", "NRML": "MARGIN", "CO": "CO", "BO": "BO"}
        if product in dict_product_type.keys():
            product = dict_product_type[product]
        else:
            product = "INTRADAY"

        #Modify the order type
        dict_order_type = {"LIMIT":1, "MARKET":2, "SL-M":3, "SL":4}
        if order_type in dict_order_type.keys():
            order_type = dict_order_type[order_type]
        else:
            order_type = 1

        #modify variety
        amo = amo.lower()
        offlineorder = True if amo == "yes" else False

        #create request dictionary
        dict_request = {"symbol": tradingsymbol,
                        "qty": quantity,
                        "type": order_type,
                        "side": t_type,
                        "productType": product,
                        "limitPrice": price,
                        "stopPrice": trigger_price,
                        "validity": validity,
                        "disclosedQty":disclosed_quantity,
                        "offlineOrder": offlineorder,
                        "stopLoss": sl_price,
                        "takeProfit": profit_price
                        }
        print("Dict Request: ", dict_request)
        # place the order
        retry_number = 1
        while retry_number <= FYERS_API_RETRY_COUNT:
            try:
                response = self.fyers.place_order(dict_request)
                print("Response: ", response)
                order_id = response['id']
                print("order_id: ", order_id)
                if not order_id == "":
                    break
                else:
                    retry_number = retry_number + 1
                    time.sleep(FYERS_API_RETRY_TIME)
            except:
                print("Exception occurred while placing order", tradingsymbol, " amo = ", amo)
                traceback.print_exc()
                retry_number = retry_number + 1
                time.sleep(FYERS_API_RETRY_TIME)

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
        # for testing
        # variety = "amo"
        resp_order_id = ""
        retry_number = 1
        dict_request = {
            "id": order_id,
            "type": 1,
            "limitPrice": price,
            "stopLoss": trigger_price
        }
        while retry_number <= FYERS_API_RETRY_COUNT:
            try:
                response = self.fyers.modify_order(dict_request)

                if response["s"] == "ok":
                    resp_order_id = order_id
                    break
                else:
                    retry_number = retry_number + 1
                    time.sleep(FYERS_API_RETRY_TIME)
            except:
                print("Exception occurred while modifying order", order_id)
                traceback.print_exc()
                retry_number = retry_number + 1
                time.sleep(FYERS_API_RETRY_TIME)
        return resp_order_id

    def cancel_order(self, order_id, variety="regular", parent_order_id=None):
        retry_number = 1
        resp_order_id = ""
        # for testing
        # variety = "amo"
        resp_order_id = ""
        dict_request = {"id": order_id}
        while retry_number <= FYERS_API_RETRY_COUNT:
            try:
                response = self.fyers.cancel_order(dict_request)
                print("response", response)
                if response["s"] == "ok":
                    resp_order_id = order_id
                    break
                else:
                    retry_number = retry_number + 1
                    time.sleep(FYERS_API_RETRY_TIME)
            except:
                print("Exception occurred while cancelling order", order_id)
                traceback.print_exc()
                retry_number = retry_number + 1
                time.sleep(FYERS_API_RETRY_TIME)

        return resp_order_id

    # order info - start
    def getOrderInfo(self, type="symbol"):
        retry_number = 1
        dict_order_data = {}
        while retry_number < FYERS_API_RETRY_COUNT:
            try:
                response = self.fyers.orderbook()
                if not response == None and response['s'] == 'ok':
                    dict_order_status = {1: ORDER_STATUS_CANCELED, 2: ORDER_STATUS_COMPLETE, \
                                         3: ORDER_STATUS_INVALID_STATUS_TYPE, 4: ORDER_STATUS_OPEN, \
                                         5: ORDER_STATUS_REJECTED, 6: ORDER_STATUS_PENDING, 7: ORDER_STATUS_CANCELED}
                    for order in response['orderBook']:
                        tsym = order['symbol'].replace("NSE:","")
                        obj_order_data = order_data
                        obj_order_data.stock = tsym
                        obj_order_data.trans_type = "B" if order['side'] == 1 else "S"
                        obj_order_data.quantity = order['qty']
                        if order['status'] in dict_order_status:
                            obj_order_data.status = dict_order_status[order['status']]
                        else:
                            obj_order_data.status = ORDER_STATUS_INVALID_STATUS_TYPE
                        obj_order_data.order_no = order['id']
                        # set the key based on type
                        key = tsym if type == 'symbol' else order['id']
                        if not key in dict_order_data:
                            lst_order_data = []
                            lst_order_data.append(obj_order_data)
                            dict_order_data[key] = lst_order_data
                        else:
                            dict_order_data[key].append(obj_order_data)

            except:
                retry_number = retry_number + 1
                time.sleep(FYERS_API_RETRY_TIME)
        return dict_order_data

    def getOrderInfoByOrderId(self, order_id):

        # place the order
        retry_number = 1
        dict_request = {"id": order_id}
        data = self.fyers.orderbook(dict_request)

        # check whether order id complete or not
        status = data['orderBook'][0]['status']
        if status == 2 or status == 4:
            status = DEFINE_TRADE_COMPLETE
        # check whether order is cancelled or rejected
        elif status == 6:
            status = DEFINE_TRADE_OPEN
        else:
            status = DEFINE_NOT_TRADED

        #check whether it is buy or sell
        if data['orderBook'][0]['side'] == -1:
            transaction_type = "sell"
        else:
            transaction_type = "buy"


        cls_order_info = order_info(stock=data['orderBook'][0]['ex_sym'],
                                    transaction_type=transaction_type,
                                    price=data['orderBook'][0]['limitPrice'], status=status)

        return cls_order_info

    def get_quotes(self, p_lst_stocks):
        retry_number = 1
        data = ""
        dict_quote_data = {}
        response = None
        #minimum one stock should be availaible

        if len(p_lst_stocks) > 0:
            request_by_full_symbol = {}
            for q_data in p_lst_stocks:
                #print("quote_data: ", q_data)
                full_symbol = self.__format_fyers_symbol(q_data.symbol, market_type=q_data.market_type)
                request_by_full_symbol[full_symbol] = q_data
                if data == "":
                    data = data + full_symbol
                else:
                    data = data + "," + full_symbol

            dict_request = {
                "symbols": data
            }
            while retry_number < FYERS_API_RETRY_COUNT:
                try:
                    response = self.fyers.quotes(data=dict_request)
                    if response.get('s') == 'ok':
                        for item in response['d']:
                            value = item.get('v', {})
                            returned_symbol = item.get('n', value.get('symbol', ''))
                            request_data = request_by_full_symbol.get(returned_symbol, get_quote_request_data(returned_symbol.replace("NSE:", ""), ""))
                            obj_quote_data = quote_data(value.get('ask', 0.0), value.get('open_price', 0.0),
                                                        value.get('high_price', 0.0), value.get('low_price', 0.0),
                                                        value.get('prev_close_price', 0.0), value.get('lp', 0.0),
                                                        value.get('volume', 0.0), value.get('bid', 0.0),
                                                        value.get('ch', 0.0), value.get('chp', 0.0),
                                                        value.get('spread', 0.0),
                                                        value.get('atp', value.get('vwap', 0.0)),
                                                        value.get('tt', 0), value.get('symbol', returned_symbol),
                                                        value)

                            for key in self.__quote_key_aliases(returned_symbol, request_data.symbol, request_data.market_type):
                                dict_quote_data[key] = obj_quote_data
                        break
                    else:
                        print("FYERS quotes error: ", response.get("code"), response.get("message"))
                        retry_number = retry_number + 1
                        time.sleep(FYERS_API_RETRY_TIME)

                except Exception as exc:
                    print("Exception while getting quotes:", exc)
                    retry_number = retry_number + 1
                    time.sleep(FYERS_API_RETRY_TIME)
        return dict_quote_data
    # order info - end

    def getOptionChain(self, symbol, exchange="NSE"):

        symbol = f"{exchange}:{symbol}"

        retry_number = 1
        dict_request = {
            "symbol": symbol,
            "strikecount": 50,   # strikes above & below ATM
            "greeks": "1"
        }
        while retry_number < FYERS_API_RETRY_COUNT:
            try:
                response = self.fyers.optionchain(data=dict_request)
                # Convert to DataFrame
                #print("Response: ", response)
                if response['s'] == 'ok':
                    return pd.DataFrame(response["data"]["optionsChain"]), response["data"]["callOi"], response["data"]["putOi"]
                else:
                    retry_number = retry_number + 1
                    time.sleep(FYERS_API_RETRY_TIME)

            except:
                print("Exception while getting option chain", response)
                retry_number = retry_number + 1
                time.sleep(FYERS_API_RETRY_TIME)
        return {"optionsChain": []}, 0, 0

    #non trading apis - start
    def convert_to_option_date_format(self, str_date, is_month_expiry):
        l_str_year = ""
        l_str_month = ""
        l_str_date = ""
        lst_split_date = str_date.split("-")
        l_str_year = lst_split_date[0]
        #get last two digits from year
        l_str_year = l_str_year[len(l_str_year) - 2:]
        l_str_month = lst_split_date[1]

        #if month is less than 10 then remove 0
        if int(l_str_month) < 10:
            l_str_month = l_str_month.replace("0", "")
        #if the date is month expiry then convert month to 3 letters (Ex: MAR) format
        if is_month_expiry:
            Months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
            l_str_month = Months[int(l_str_month) - 1]
        else:
            l_str_date = lst_split_date[2]

        return (l_str_year + l_str_month + l_str_date)

