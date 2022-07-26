from peewee import *
from datetime import date, timedelta, datetime
import numpy as np 
import pandas as pd
import seaborn as sns
import time
import json
import yaml
from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
from pandas.plotting import register_matplotlib_converters

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

#Persist info
db= SqliteDatabase('assets.db')

class BaseModel(Model):
    class Meta:
        database = db

class Run(BaseModel): # This model uses the "assets.db" database.
    timestamp = DateTimeField(unique=True)
    symbol = CharField()
    id = AutoField()

class Price(BaseModel): # This model uses the "assets.db" database.
    datetime = DateTimeField(unique=True)
    volume_24 = FloatField()
    price = FloatField()
    runid = ForeignKeyField(Run, backref='prices')

# By default, Peewee includes an IF NOT EXISTS clause when creating tables. 
def create_tables():
    with db:
        db.create_tables([Price])
        db.create_tables([Run])

def drop_tables():
    with db:
        db.drop_tables([Price])
        db.drop_tables([Run])

create_tables()

symbol = 'RBTCUSD'
query_interval = 10
query_number = 100

with open(r'api_config_coinmarketcap.yml') as file:
    apikey = yaml.load(file, Loader=yaml.FullLoader)['api_key']

# Define some essential API parameters
# Coinmarketcap API for latest market ticker quotes and averages for cryptocurrencies and exchanges.
# https://coinmarketcap.com/api/documentation/v1/#operation/getV1CryptocurrencyListingsLatest
url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
parameters = {
  'start':'1',
  'limit':'1',
  'convert':'USD'
}
headers = {
  'Accepts': 'application/json',
  'X-CMC_PRO_API_KEY': apikey,
}

session = Session()
session.headers.update(headers)

# create a new run and save it to our local SQLite DB
run_timestamp = datetime.now()
run = Run(symbol=symbol, timestamp = run_timestamp)
run.save()
current_run_id = run.id 
print(f'run_id: {current_run_id} - timestamp: {run_timestamp} - interval: {query_interval} - number of queries: {query_number}')

# query the coinmarketcap API every x seconds
for s in range(0, query_number):
    try:
        response = session.get(url, params=parameters)
        data = json.loads(response.text)
        #print(data)
        
        # response - quote
        data_quote = data['data'][0]['quote']['USD']
        price = np.round(data_quote['price'], 1) # the price
        volume_24 = np.round(data_quote['volume_24h'], 1) # the volume in the last 24 hours
        
        # response - status
        data_status = data['status']
        api_timestamp = data_status['timestamp'] # the timestamp of the pricepoint
        api_credits = data_status['credit_count'] # the number of credits spent on the last request
        
        # create a new pricepoint and save it to the SQLite db
        new_pricepoint = Price(datetime=api_timestamp, price=price, volume_24=volume_24, runid=current_run_id)
        id = new_pricepoint.save()

        # display what we have just saved
        print(f'request number: {s} - added {price} at {api_timestamp} - 24 hour volume: {volume_24} - credits used: {api_credits}')      

    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)
    time.sleep(query_interval)
    query = Run.select().where(Run.id==current_run_id)
    run_overview = pd.DataFrame(list(query.dicts()))
    query = Price.select().where(Price.runid==current_run_id)
df_prices = pd.DataFrame(list(query.dicts()))
print(df_prices)

register_matplotlib_converters()
fig, ax = plt.subplots(figsize=(10, 8))
plt.title('BTC prices from the coinmarketcap API', fontsize=14)
datetimes = pd.to_datetime(df_prices['datetime'])

sns.lineplot(data=df_prices, x=datetimes, y="price")
#ax.set_xlim([df_prices['datetime'].min(),df_prices['datetime'].max()])
#ax.xaxis.set_major_locator(mdates.MinuteLocator())
plt.xticks(rotation=75)
