import json
import logging
import math
import time
import urllib.parse
from functools import reduce, cache

import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import matplotlib.pyplot as plt


@cache
def getTickerByCompanyNameViaGoogle(company: str):
    options = Options()
    ser = Service("D:/Developer/PycharmProjects/GlassdoorStockProjection/chromedriver.exe")
    options.headless = True
    driver = webdriver.Chrome(options=options)

    driver.get(f"https://www.google.com/search?q={urllib.parse.quote_plus(company)}+stock")

    if len(driver.find_elements(By.XPATH, "//*[@data-attrid='Ticker Symbol']")) == 0:
        elements = driver.find_elements(By.CSS_SELECTOR, "g-more-link")
        if len(elements) > 0:
            try:
                elements[0].click()
            except ElementNotInteractableException:
                logging.debug(f"Element not interactable: {elements[0]}")

    elements = driver.find_elements(By.XPATH, "//*[@data-attrid='Ticker Symbol']")
    ticker = None
    if len(elements) > 0:
        logging.info(f"Found ticker for {company} - {elements[0].text}")
        ticker = elements[0].text
    else:
        logging.debug(f"No ticker found for {company}")

    driver.quit()
    return ticker


def getBestPlacesToWorkFromLinkedIn(year: int) -> list[str]:
    if year == datetime.now().year:
        url = "https://www.glassdoor.com/Award/Best-Places-to-Work-LST_KQ0,19.htm"
    elif year >= 2009:
        url = f"https://www.glassdoor.com/Award/Best-Places-to-Work-{year}-LST_KQ0,24.htm"
    else:
        logging.error("Year must be greater than 2009")
        return []

    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36",
    }

    response = requests.request("GET", url, headers=headers)

    while response.status_code != 200:
        logging.debug(f"Call failed for year {year}. Retrying in 1 second...")
        response = requests.request("GET", url, headers=headers)
        time.sleep(1)

    soup = BeautifulSoup(response.content, features="lxml")
    bestPlacesToWork = []
    for a_tag in soup.find_all(class_="h2 m-0 strong"):
        bestPlacesToWork.append(a_tag.text)

    return bestPlacesToWork


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    initialCapital = 10_000
    numInvestments = 10

    years = [2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021]

    overallPlot = []

    currentCapital = initialCapital
    for year in years:
        companies = getBestPlacesToWorkFromLinkedIn(year)[:50]
        tickers = [getTickerByCompanyNameViaGoogle(company) for company in companies]

        yearlyReturns = []
        yearlySpend = 0

        for company, symbol in zip(companies, tickers):
            if symbol is None:
                continue

            ticker = yf.Ticker(symbol.split(":")[1].strip())
            historicPrice = ticker.history(start=f"{year}-01-01", end=f"{year + 1}-01-01")
            amountToInvestInThisStock = currentCapital / numInvestments
            if len(historicPrice.head(1)["Close"].values) == 0:
                continue
            yearBeginPrice = historicPrice.head(1)["Close"].values[0]
            # allow overages
            sharesToBuy = math.ceil(amountToInvestInThisStock / yearBeginPrice)

            yearlyReturns.append(historicPrice["Close"] * sharesToBuy)
            yearlySpend += yearBeginPrice * sharesToBuy

            logging.info(f"Bought {sharesToBuy} shares of {symbol} at ${yearBeginPrice} a share for a total of ${yearBeginPrice * sharesToBuy}")

            if len(yearlyReturns) >= numInvestments:
                break

        d = reduce(lambda x, y: x.add(y, fill_value=0), yearlyReturns)
        d = d.to_frame()

        overallPlot.append(d)

        endOfYearValue = d.tail(1)["Close"].values[0]
        logging.info(f"For year {year}, brought ${yearlySpend} -> ${endOfYearValue} for a gain of ${endOfYearValue - yearlySpend}")
        currentCapital = endOfYearValue

    ax = plt.subplot()
    for d, year in zip(overallPlot, years):
        d.plot(ax=ax, label=year)

    ticker = yf.Ticker("^GSPC")
    historicPrice = ticker.history(start=f"{years[0]}-01-01", end=f"{years[-1] + 1}-01-01")
    yearBeginPrice = historicPrice.head(1)["Close"].values[0]
    sharesToBuy = math.ceil(initialCapital / yearBeginPrice)
    historicPrice = historicPrice["Close"] * sharesToBuy
    historicPrice.plot(ax=ax, label="S&P 500")

    ax.legend(years + ["S&P 500"], loc='upper center', bbox_to_anchor=(0.5, 1.05),
              ncol=3, fancybox=True, shadow=True)
    plt.savefig("overall.png")
