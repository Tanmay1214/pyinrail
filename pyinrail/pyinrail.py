import os
import json
import time
from io import BytesIO
import requests
import demjson3
import pytesseract
import pandas as pd
from PIL import Image
from fuzzywuzzy import process

from .utils import *


class RailwayEnquiry:
    """
    The railway enquiry class which has methods to fetch various enquiry details
    """

    def __init__(self, src=None, dest=None, date=None):
        self.session = {}
        
        stations_path = os.path.join(os.path.dirname(__file__), 'stations.json')
        if not os.path.exists(stations_path):
            self.load_stations()
        with open(stations_path, 'r') as f:
            self.stations = json.load(f)
        
        trains_path = os.path.join(os.path.dirname(__file__), 'trains.json')
        if not os.path.exists(trains_path):
            self.load_trains()
        with open(trains_path, 'r') as f:
            self.trains = json.load(f)
        
        self.src = self.get_stn_code(src) if src else None
        self.dest = self.get_stn_code(dest) if dest else None
        self.date = date
        
        self.create_session()

    def create_session(self):
        """Create a session by solving captcha challenge"""
        self.session['timestamp'] = int(time.time() * 1000)
        url = f"http://www.indianrail.gov.in/enquiry/captchaDraw.png?{self.session['timestamp']}"
        r = requests.get(url)
        self.session['cookies'] = r.cookies
        try:
            im = Image.open(BytesIO(r.content))
            text = pytesseract.image_to_string(im, lang='eng')
            self.session['captcha'] = eval(text.split("=")[0])
        except:
            self.create_session()
    
    def get_stn_code(self, query):
        """Get correct station code"""
        query = query.upper()
        if query in self.stations:
            return self.stations[query]
        return process.extractOne(query, self.stations.values())[0]

    def get_trains_between_stations(self, src=None, dest=None, date=None, as_df=False):
        """Get trains between source and destination stations"""
        src = self.get_stn_code(src) if src else self.src
        dest = self.get_stn_code(dest) if dest else self.dest
        date = date if date else self.date

        if not all([src, dest, date]):
            return "Source, destination, or date is empty!"
        
        params = {
            "inputCaptcha": self.session['captcha'],
            "dt": date,
            "sourceStation": src,
            "destinationStation": dest,
            "language": "en",
            "inputPage": "TBIS",
            "flexiWithDate": "y",
            "_": self.session['timestamp']
        }
        r = requests.get(API_ENDPOINT, params=params, cookies=self.session['cookies'])
        try:
            data = r.json()['trainBtwnStnsList']
        except:
            if 'errorMessage' in r.json() and r.json()['errorMessage'] == "Session out or Bot attack":
                self.create_session()
                return self.get_trains_between_stations(src, dest, date)
            return r.json().get('errorMessage', 'Unknown error')
        
        if as_df:
            return pd.DataFrame(data)
        return data
    
    def get_seat_availability(self, train_no, classc='SL', quota='GN', src=None, dest=None, date=None, as_df=False):
        """Get seat availability in a train"""
        src = self.get_stn_code(src) if src else self.src
        dest = self.get_stn_code(dest) if dest else self.dest
        date = date if date else self.date

        if not all([src, dest, date]):
            return "Source, destination, or date is empty!"

        params = {
            "inputCaptcha": self.session['captcha'],
            "trainNo": str(train_no),
            "classc": classc,
            "quota": quota,
            "dt": date,
            "sourceStation": src,
            "destinationStation": dest,
            "language": "en",
            "inputPage": "SEAT",
            "_": self.session['timestamp']
        }
        r = requests.get(API_ENDPOINT, params=params, cookies=self.session['cookies'])
        try:
            data = r.json()['avlDayList']
        except:
            if 'errorMessage' in r.json() and r.json()['errorMessage'] == "Session out or Bot attack":
                self.create_session()
                return self.get_seat_availability(train_no, classc, quota, src, dest, date)
            return r.json().get('errorMessage', 'Unknown error')
        
        if as_df:
            return pd.DataFrame(data)
        return data
    
    def get_pnr_status(self, pnr_no):
        """Get PNR status"""
        params = {
            "inputCaptcha": self.session['captcha'],
            "inputPnrNo": pnr_no,
            "language": "en",
            "inputPage": "PNR",
            "_": self.session['timestamp']
        }
        r = requests.get(API_ENDPOINT, params=params, cookies=self.session['cookies'])
        try:
            return r.json()
        except:
            if 'errorMessage' in r.json() and r.json()['errorMessage'] == "Session out or Bot attack":
                self.create_session()
                return self.get_pnr_status(pnr_no)
            return r.json().get('errorMessage', 'Unknown error')
