# -*- coding: utf-8 -*-
"""
login_types.py
"""
from dataclasses import dataclass

@dataclass
class LogInData:
    broker: str = ""
    user_id: str = ""
    password: str = ""
    api_key: str = ""
    api_secret_key: str = ""
    phone_no: str = ""
    totp_key: str = ""

    def __init__(self, broker:str, user_id:str, password:str, api_key:str, api_secret_key:str, phone_no:str, totp_key:str):
        self.broker = broker
        self.user_id = user_id
        self.password = password
        self.api_key = api_key
        self.api_secret_key = api_secret_key
        self.phone_no = phone_no
        self.totp_key = totp_key

