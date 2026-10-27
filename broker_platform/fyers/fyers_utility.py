# -*- coding: utf-8 -*-
"""
Fyers utility
"""

#from fyers_apiv3 import accessToken
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws
import traceback
#from utility import *
import pyotp
from datetime import *
import calendar
from selenium import webdriver
from selenium.webdriver.common.by import By
import webbrowser
import hashlib
import time
import requests
from requests.adapters import HTTPAdapter
from DataTypes.defines import *
from DataTypes.trade_data import quote_data
import datetime as dt
from zoneinfo import ZoneInfo
import threading
import queue
import yaml
from yaml import SafeLoader
import pandas as pd

IST = ZoneInfo("Asia/Kolkata")

#Define
FYERS_API_RETRY_COUNT = 5
FYERS_API_RETRY_TIME = 1
FYERS_HISTORY_REQUEST_INTERVAL_SECONDS = 1.75
FYERS_INVALID_SYMBOL_ERROR = 'Please provide a valid symbol'
# The static IPv4 whitelisted for this app on myapi.fyers.in. Fyers rejects orders from any other
# IP ("Algo orders are not allowed from this app", code -50). If set, the machine's public IPv4 is
# checked against it before each order; leave "" to skip the check.
FYERS_STATIC_IPV4 = "106.51.205.25"
FYERS_IPV4_CHECK_URL = "https://api.ipify.org"

# Fyers' trading API (orders, positions, funds...). Market data lives under /data instead.
FYERS_TRADING_API_PREFIX = "https://api-t1.fyers.in/api/v3/"
# Fyers rejects orders that don't arrive from the whitelisted IP (code -50); retrying can't help.
FYERS_IP_REJECTED_CODE = -50

_fyers_history_rate_lock = threading.Lock()
_fyers_history_next_request_at = 0.0
_fyers_data_websocket_lock = threading.Lock()
_fyers_data_websocket_instance = None


def _wait_for_fyers_history_slot():
    """Space history request starts to stay below Fyers Standard's 50/minute limit."""
    global _fyers_history_next_request_at
    with _fyers_history_rate_lock:
        now = time.monotonic()
        request_at = max(now, _fyers_history_next_request_at)
        _fyers_history_next_request_at = request_at + FYERS_HISTORY_REQUEST_INTERVAL_SECONDS
    delay = request_at - now
    if delay > 0:
        time.sleep(delay)


class _IPv4Adapter(HTTPAdapter):
    """
    Connection pool whose sockets are bound to an IPv4 source address, so requests through it
    always leave over IPv4. On a dual-stack network requests prefers IPv6, and Fyers would see the
    IPv6 address instead of the whitelisted static IPv4. A pool of its own also matters: the
    session's existing keep-alive connections to api-t1.fyers.in (opened by history/quote calls,
    over IPv6) would otherwise be reused for orders.
    """

    def init_poolmanager(self, *args, **kwargs):
        kwargs["source_address"] = ("0.0.0.0", 0)
        super().init_poolmanager(*args, **kwargs)


def _check_static_ipv4():
    # Warns if the public IPv4 isn't the whitelisted one -- the order is still sent, Fyers stays
    # the authority on whether it's accepted.
    if not FYERS_STATIC_IPV4:
        return
    try:
        session = requests.Session()
        session.mount("https://", _IPv4Adapter())
        public_ip = session.get(FYERS_IPV4_CHECK_URL, timeout=5).text.strip()
    except Exception:
        print("Could not determine public IPv4 before placing order")
        return
    if public_ip != FYERS_STATIC_IPV4:
        print("WARNING: public IPv4", public_ip, "is not the whitelisted static IP", FYERS_STATIC_IPV4,
              "-- Fyers will likely reject this order")


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


class fyers_data_websocket:
    """FYERS full-mode SymbolUpdate socket and thread-safe tick store."""

    def __init__(self, client_id, access_token, logs_path):
        self.client_id = client_id
        self.access_token = access_token
        self.logs_path = logs_path
        self._fyers = None
        self._ticks = []
        self._incoming_ticks = queue.SimpleQueue()
        self._tick_lock = threading.Lock()
        self._subscription_lock = threading.RLock()
        self._desired_symbols = set()
        self._active_symbols = set()
        self._is_connected = False
        self._is_started = False
        self._is_closed = False
        self._subscription_queue = queue.Queue()
        self._subscription_thread = threading.Thread(
            target=self._process_subscription_queue,
            name="fyers-data-subscriptions",
            daemon=True,
        )
        self._subscription_thread.start()

    def connect(self):
        with self._subscription_lock:
            if self._is_started or self._is_closed:
                return
            self._is_started = True
            self._fyers = data_ws.FyersDataSocket(
                access_token=f"{self.client_id}:{self.access_token}",
                write_to_file=False,
                log_path=self.logs_path,
                litemode=False,
                reconnect=True,
                on_message=self._on_message,
                on_error=self._on_error,
                on_connect=self._on_connect,
                on_close=self._on_close,
                reconnect_retry=5,
            )

        try:
            self._fyers.connect()
        except Exception:
            print("Exception while connecting Fyers data WebSocket")
            traceback.print_exc()
            with self._subscription_lock:
                self._is_started = False

    def subscribe(self, p_lst_symbols):
        lst_symbols = [symbol for symbol in p_lst_symbols if symbol]
        if not lst_symbols:
            return
        with self._subscription_lock:
            if self._is_closed:
                return
            self._desired_symbols.update(lst_symbols)
            is_started = self._is_started
            is_connected = self._is_connected
        if not is_started:
            self.connect()
        elif is_connected:
            self._subscription_queue.put("refresh")

    def unsubscribe(self, p_lst_symbols):
        lst_symbols = [symbol for symbol in p_lst_symbols if symbol]
        if not lst_symbols:
            return
        with self._subscription_lock:
            self._desired_symbols.difference_update(lst_symbols)
            is_connected = self._is_connected
        if is_connected:
            self._subscription_queue.put("refresh")

    def _on_connect(self):
        with self._subscription_lock:
            if self._is_closed:
                fyers = self._fyers
                should_close = True
            else:
                should_close = False
                self._is_connected = True
                # The 3.1.14 SDK clears its channel state before reconnecting;
                # rebuild it from our desired symbol set after each connect.
                self._active_symbols.clear()
                fyers = self._fyers
        if should_close:
            if fyers is not None:
                fyers.close_connection()
            return
        print("Fyers data WebSocket connected")
        if fyers is not None:
            fyers.keep_running()
        self._subscription_queue.put("refresh")

    def _on_message(self, message):
        if not isinstance(message, dict) or "symbol" not in message:
            return
        tick = dict(message)
        tick["received_at"] = datetime.now(IST)
        self._incoming_ticks.put(tick)

    def _on_error(self, message):
        print("Fyers data WebSocket error:", message)

    def _on_close(self, message):
        with self._subscription_lock:
            self._is_connected = False
        print("Fyers data WebSocket closed:", message)

    def _process_subscription_queue(self):
        while True:
            command = self._subscription_queue.get()
            if command is None:
                return
            with self._subscription_lock:
                if self._is_closed or not self._is_connected or self._fyers is None:
                    continue
                fyers = self._fyers
                active_symbols = set(self._active_symbols)
                desired_symbols = set(self._desired_symbols)

            if active_symbols == desired_symbols:
                continue
            if active_symbols:
                fyers.unsubscribe(sorted(active_symbols), data_type="SymbolUpdate")
            if desired_symbols:
                fyers.subscribe(sorted(desired_symbols), data_type="SymbolUpdate")

            with self._subscription_lock:
                if self._is_connected and not self._is_closed:
                    self._active_symbols = desired_symbols

    def get_tick_data(self):
        with self._tick_lock:
            while True:
                try:
                    self._ticks.append(self._incoming_ticks.get_nowait())
                except queue.Empty:
                    break
            ticks = [dict(tick) for tick in self._ticks]
        return pd.DataFrame.from_records(ticks)

    def close(self):
        with self._subscription_lock:
            if self._is_closed:
                return
            self._is_closed = True
            self._is_connected = False
            self._desired_symbols.clear()
            fyers = self._fyers

        if fyers is not None:
            try:
                # In this SDK version close_connection() also stops reconnects
                # and joins its WebSocket, message, and ping threads.
                if not fyers.is_connected():
                    # close_connection() is a no-op before the SDK has a
                    # socket object; disable a pending auto-reconnect as well.
                    fyers.restart_flag = False
                fyers.close_connection()
            except Exception:
                print("Exception while closing Fyers data WebSocket")
                traceback.print_exc()

        self._subscription_queue.put(None)
        if threading.current_thread() is not self._subscription_thread:
            self._subscription_thread.join(timeout=5)


class fyers_utitlity:
    # fetchOHLC/get_quotes append "-{market_type}" to the ticker for any non-"", non-"FUT" value
    # (see fetchOHLC below) -- option symbols from get_option_name are already complete Fyers
    # trading symbols, so they need the EMPTY sentinel here (opposite of Zebu/Kite, which need a
    # non-empty one to avoid their own reparse-as-option logic).
    OPTION_MARKET_TYPE = ""

    def __init__(self, user_name, client_id, secret_id, pin, totp, phone_no, refresh_token=""):
        #generate trading session
        self.data_websocket = None
        try:
            self.is_running = False
            self.logs_path = os.getcwd() + "/Logs/"
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
            #self.access_token = self.__get_access_token_by_refresh_token()
            self.access_token = self.__getAccessToken()
            print("AppID: ", self.app_id, "Access Token: ", self.access_token)
            # FyersModel opens fyersApi.log/fyersRequests.log under log_path via
            # logging.FileHandler, which raises FileNotFoundError if the dir doesn't exist yet.
            os.makedirs(self.logs_path, exist_ok=True)
            self.fyers = fyersModel.FyersModel(client_id=self.app_id, token=self.access_token,log_path=self.logs_path)
            # orders (and the rest of the trading API) over IPv4 only -- see _IPv4Adapter
            self.fyers.service.session.mount(FYERS_TRADING_API_PREFIX, _IPv4Adapter())
            self.is_running = True
            print("Fyers utility initialized")
            time.sleep(5)
        except Exception:
            print("Exception in fyers utility constructor")
            traceback.print_exc()

    def get_running_status(self):
        return self.is_running

    def get_data_websocket(self):
        global _fyers_data_websocket_instance
        with _fyers_data_websocket_lock:
            if self.data_websocket is not None and not self.data_websocket._is_closed:
                return self.data_websocket

            if (_fyers_data_websocket_instance is None
                    or _fyers_data_websocket_instance._is_closed):
                _fyers_data_websocket_instance = fyers_data_websocket(
                    client_id=self.app_id,
                    access_token=self.access_token,
                    logs_path=self.logs_path,
                )
            elif (_fyers_data_websocket_instance.client_id != self.app_id
                  or _fyers_data_websocket_instance.access_token != self.access_token):
                raise RuntimeError("Only one FYERS data WebSocket account is supported per process")

            self.data_websocket = _fyers_data_websocket_instance
        return self.data_websocket

    @staticmethod
    def get_data_websocket_symbol(p_symbol, p_market_type):
        symbol = "NSE:" + p_symbol
        if p_market_type not in ("", "FUT"):
            symbol += "-" + p_market_type
        return symbol

    def __get_access_token_by_refresh_token(self):
        hash_val = hashlib.sha256(f"{self.app_id}:{self.secret_id}".encode())
        access_token = ""
        data = {
            "grant_type": "refresh_token",
            "appIdHash": hash_val.hexdigest(),
            "refresh_token": self.refresh_token,
            "pin": self.pin
        }
        response = requests.post(
            'https://api-t1.fyers.in/api/v3/validate-refresh-token', headers="", json=data
        )
        response = response.json()
        print("response: ", response)
        if response['s'] == 'ok':
            access_token = response['access_token']
            self.is_running = True
        else:
            print("Execute fyers generate token python script")
        return access_token

    def __getAccessToken(self):
        try:
            appSession = fyersModel.SessionModel(client_id=self.app_id,
                                                  secret_key=self.secret_id,
                                                  redirect_uri="http://google.com/",
                                                  response_type="code",
                                                  grant_type="authorization_code")
            tokenURL = appSession.generate_authcode()
            print("tokenURL: ", tokenURL)
            time.sleep(1)
            # This command is used to open the url in default system brower
            #authUrl = self.__get_url_token(tokenURL)
            authUrl = self.__get_url_token_manual(tokenURL)
            #print("authUrl: ", authUrl)
            appSession.set_token(authUrl)
            generate_token = appSession.generate_token()
            print("Generate Token - ", generate_token)
            return generate_token['access_token']
        except:
            traceback.print_exc()

    def __get_totp(self):
        totp = pyotp.TOTP(self.totp)
        # Wait until a fresh OTP window if current one is about to expire
        remaining = totp.interval - (int(time.time()) % totp.interval)

        if remaining <= 30:
            print(f"Waiting {remaining + 1} seconds for a fresh OTP...")
            time.sleep(remaining + 1)
        return totp.now()

    def __get_url_token_manual(self, str_url):
        print("URL: ", str_url)
        print("Use this Phone Number, TOTP and pin for login in Web Browser: ", self.phone_no,  self.__get_totp(), self.pin)
        authUrl = input('Open url and get the URL from redirect URL and use above totp for login')
        return authUrl.split('auth_code=')[1].split('&state')[0]

    def __get_url_token(self, str_url):
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
            # calendar.month_abbr entries are title-case ("Aug"); callers may pass all-caps
            # (e.g. datetime.strftime("%d-%b-%Y").upper()), so normalize before the lookup --
            # otherwise .index() raises ValueError for anything but exact title-case input.
            l_str_month = str(list(calendar.month_abbr).index(l_str_month.capitalize()))

        # if month is less than 10 then remove 0
        if int(l_str_month) < 10:
            l_str_month = l_str_month.replace("0", "")
        # if the date is month expiry then convert month to 3 letters (Ex: MAR) format
        if is_month_expiry:
            Months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
            l_str_month = Months[int(l_str_month) - 1]
        else:
            # Fyers weekly month codes: 1-9 for Jan-Sep, O/N/D for Oct/Nov/Dec
            Months = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "O", "N", "D"]
            l_str_month = Months[int(l_str_month) - 1]
            l_str_date = lst_split_date[0]


        return (l_str_year + l_str_month + l_str_date)

    def get_future_name(self, symbol: str, expiry_date: str):
        # Fyers monthly future convention: {SYMBOL}{YY}{MMM}FUT, e.g. NIFTY26AUGFUT.
        # No exchange prefix here -- fetchOHLC/place_order prepend "{exchange}:" themselves.
        split_data = expiry_date.split("-")
        return f"{symbol}{split_data[2][-2:]}{split_data[1].upper()}FUT"

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

        #modifying ticker
        ticker = exchange + ":" + ticker
        if ticker == "NIFTY50":
            ticker = "NIFTY"
        if market_type == "FUT":
            # future symbols (from get_future_name) are already complete Fyers trading
            # symbols, e.g. NIFTY26AUGFUT -- no suffix needed.
            pass
        elif not market_type == "":
            #for options market is not required
            ticker = ticker + "-" + market_type
        else:
            if ticker.endswith("CE-INDEX") or ticker.endswith("PE-INDEX"):
                ticker = ticker.replace("-INDEX", "")


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
        data = []
        response = None
        dict_request = {"symbol": ticker, "resolution": interval, "date_format": "1", "range_from": str_from_date,
                        "range_to": str_to_date, "cont_flag": "1"}
        print(dict_request)
        while retry_number < FYERS_API_RETRY_COUNT:
            try:
                _wait_for_fyers_history_slot()
                response = self.fyers.history(dict_request)
                #print("Response: ", response)
                historic_data_col = [DATE_TIME, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE,VOLUME_DATA]
                if response['s'] == 'ok':
                    data = pd.DataFrame.from_dict(response['candles'])
                    # F&O candles carry a trailing open-interest field that equity/index candles
                    # don't -- keep only the columns we actually name.
                    data = data.iloc[:, :len(historic_data_col)]
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
                    print("Error Response: ", dict_request, response)
                    data = pd.DataFrame()
                    # code -300 "Invalid symbol provided" is permanent -- the symbol doesn't
                    # exist (e.g. an expired/delisted weekly option contract), so retrying with
                    # the same request can never succeed. Stop immediately instead of burning
                    # through all FYERS_API_RETRY_COUNT retries with a sleep between each.
                    if isinstance(response, dict) and response.get("code") == -300:
                        break
                    # 's': 'no_data' is a valid answer too -- the symbol exists but has no
                    # candles in this range (e.g. an illiquid deep ITM/OTM strike), so a retry
                    # would just return the same thing after the sleep.
                    if isinstance(response, dict) and response.get("s") == "no_data":
                        break
                    time.sleep(2)

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

    def getTimeFrame(self, str_start_time="05:30:00", str_stop_time="05:30:00", start_date=dt.datetime.now(IST).date(), stop_date=dt.datetime.now(IST).date()):
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
        exchange_prefix = exchange + ":"
        if not tradingsymbol.upper().startswith(exchange_prefix.upper()):
            tradingsymbol = exchange_prefix + tradingsymbol
        if market_type:
            tradingsymbol = tradingsymbol + "-" + market_type

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
                _check_static_ipv4()
                response = self.fyers.place_order(dict_request)
                print("Response: ", response)
                # error responses carry no 'id'
                order_id = response.get('id', "")
                print("order_id: ", order_id)
                if not order_id == "":
                    break
                elif response.get('code') == FYERS_IP_REJECTED_CODE:
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
        #minimum one stock should be availaible

        if len(p_lst_stocks) > 0:
            data = ",".join(
                self.get_data_websocket_symbol(q_data.symbol, q_data.market_type)
                for q_data in p_lst_stocks
            )

            dict_request = {
                "symbols": data
            }
            while retry_number < FYERS_API_RETRY_COUNT:
                try:
                    response = self.fyers.quotes(data=dict_request)
                    if response['s'] == 'ok':
                        for item in response['d']:
                            values = item.get('v', {})
                            obj_quote_data = quote_data(
                                values.get('ask', values.get('bid', values.get('lp', -1.0))),
                                values.get('open_price', -1.0),
                                values.get('high_price', -1.0),
                                values.get('low_price', -1.0),
                                values.get('prev_close_price', -1.0),
                                values.get('lp', -1.0),
                                values.get('volume', -1.0))

                            dict_quote_data[item['n'].replace("NSE:", "")] = obj_quote_data
                        break
                    else:
                        retry_number = retry_number + 1
                        time.sleep(FYERS_API_RETRY_TIME)

                except:
                    print("Exception while getting quotes", response)
                    traceback.print_exc()
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
        response = None
        while retry_number < FYERS_API_RETRY_COUNT:
            try:
                response = self.fyers.optionchain(data=dict_request)
                # Convert to DataFrame
                #print("Response: ", response)
                if response['s'] == 'ok':
                    return pd.DataFrame(response["data"]["optionsChain"]), response["data"]["callOi"], response["data"]["putOi"]
                else:
                    message = str(response.get("message", "")) if isinstance(response, dict) else ""
                    if "limit" in message.lower() and "requests/day" in message.lower():
                        print("Fyers option-chain request limit reached:", message)
                        break
                    retry_number = retry_number + 1
                    time.sleep(FYERS_API_RETRY_TIME)

            except Exception:
                print("Exception while getting option chain", response)
                retry_number = retry_number + 1
                time.sleep(FYERS_API_RETRY_TIME)
        return pd.DataFrame(), 0, 0

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

