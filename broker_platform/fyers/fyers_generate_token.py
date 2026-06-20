# -*- coding: utf-8 -*-
"""
Zerodha Kite Connect - Historical Data

"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]  # BrokerUtility
sys.path.insert(0, str(ROOT))

from fyers_utility import fyers_session_model

config_file = input("Enter config file path: \n")
obj_session_model = fyers_session_model(config_file)
obj_session_model.get_tokens()