from base64 import b64decode
import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
import time
from datetime import datetime
from pytz import timezone    
import streamlit as st

def get_stockx_product_metadata(variant):
  api_response = requests.post(
      "https://api.zyte.com/v1/extract",
      auth=(st.secrets["zyte_api_key"], ""),
      json={
          "url": f"https://stockx.com/search?s={variant}",
          "httpResponseBody": True,
      },
  )
  http_response_body: bytes = b64decode(
      api_response.json()["httpResponseBody"])

  soup = BeautifulSoup(http_response_body)
  url_key = soup.find("a", {"data-testid": "productTile-ProductSwitcherLink"})['href']
  title = soup.find("p", {"data-testid": "product-tile-title"}).getText()
  return url_key, title


# given a URL key and title, get the relevant stockX data.
def get_stockx_pricing(url_key, title):
  sales_data = requests.post(
      "https://api.zyte.com/v1/extract",
      auth=(st.secrets["zyte_api_key"], ""),
      json={
          "url": f"https://stockx.com{url_key}",
          "httpResponseBody": True,
      },
  )
  http_response_body: bytes = b64decode(
      sales_data.json()["httpResponseBody"])

  soup = BeautifulSoup(http_response_body)
  output_json = json.loads(soup.find('script', type="application/json").text)
  # get product variants
  # print(output_json)
  product_variants = output_json['props']['pageProps']['req']['appContext']['states']["query"]['value']['queries'][3]['state']['data']['product']['variants']
  image_url = output_json['props']['pageProps']['req']['appContext']['states']['query']['value']['queries'][-1]['state']['data']['product']['media']['imageUrl']
  output = []

  lowest_ask = 0
  highest_bid = 0

  for variant in product_variants:
    size = variant['traits']['size']

    if variant['market']['state']['lowestAsk'] is not None:
      lowest_ask = variant['market']['state']['lowestAsk']['amount']
    if variant['market']['state']['highestBid'] is not None:
      highest_bid = variant['market']['state']['highestBid']['amount']

    num_of_asks = variant['market']['state']['numberOfAsks']
    num_of_bids = variant['market']['state']['numberOfBids']
    last_sales = variant['market']['salesInformation']['lastSale']

    size_options = ''.join(str([i['size'].replace(' ','') for i in variant['sizeChart']['displayOptions']]))

    output.append({
        'size_options': size_options,
        'lowest_ask': lowest_ask,
        'highest_bid': highest_bid,
        'num_of_asks': num_of_asks,
        'num_of_bids': num_of_bids,
        'last_sales': last_sales
    })

  df = pd.DataFrame(output, columns=['size_options','lowest_ask', 'highest_bid', 'num_of_asks', 'num_of_bids', 'last_sales'])
  df['url'] = f'https://stockx.com{url_key}'
  df['title'] = title
  df['image_url'] = image_url
  return df


# Get stockx data from a variatn
def get_stockx_data(variant):
  # get url key + title name
  stockx_metadata = get_stockx_product_metadata(variant)

  # get StockX pricing
  stockx_pricing_df = get_stockx_pricing(url_key=stockx_metadata[0], title=stockx_metadata[1])
  stockx_pricing_df['variant'] = variant

  pacific_tz = timezone('US/Pacific')
  current_datetime = datetime.now(pacific_tz)
  stockx_pricing_df['stockX_data_as_of'] = current_datetime.strftime('%Y-%m-%d %H:%M:%S PST')
  return stockx_pricing_df


st.title('🔌⚡️👻')

sku_input_dfs = []
text_input = st.text_area(label='Input SKUs to search 👇')
if len(text_input) > 0:
  st.subheader('Running scraper 🔁')
  progress_text = "Operation in progress. Please wait."
  item_list = list(set(text_input.splitlines()))
  # og_df = pd.DataFrame(item_list, columns=['SKU'])
  num_of_skus = len(item_list)
  with st.status("Scraping stockX data...", expanded=True) as status:
    for idx,sku in enumerate(item_list):
      st.write(f'Scraping {sku}: {idx + 1} of {num_of_skus}')
      while True:
        try:
        #append dataframe for SKUs we care about
          sku_input_dfs.append(get_stockx_data(sku))
          time.sleep(0.1)
        except:
          st.write(f'{sku} errored - retrying 😵‍💫')
          
      status.update(label="Scraping complete!", state="complete", expanded=False)
      # output stockX dataframe
  stockx_df = pd.concat(sku_input_dfs).reset_index(drop=True)
  st.write(stockx_df)