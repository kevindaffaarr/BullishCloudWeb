#!.\env\Scripts\python.exe
import plotlyGen as pg
import getData as gd

from flask import Flask, render_template, request
import pandas as pd
import requests

app = Flask(__name__)

@app.route('/')
@app.route('/home')
@app.route('/whaleChart')
def whaleChart():
	render_template('loadingPage.html')
	# ======================================================================================================
	#INI NANTI QUERY DATABASE
	# ======================================================================================================
	exchange = ["Binance","Indonesia Stock Exchange"]
	
	url = "https://api.binance.com/api/v3/ticker/price"
	tickers = requests.get(url).text
	df = pd.read_json(tickers)
	tickers = df["symbol"].sort_values()
	
	intervals = ["1m","5m","15m","30m","1h","4h","1D","1W"]
	# ======================================================================================================
	pageTitle = "Whale Chart"
	response = {
		"pageTitle":pageTitle, 
		"exchange":exchange,
		"tickers":tickers,
		"intervals":intervals
	}
	return render_template('home.html',response=response)

@app.route('/datawhaleChart', methods=['GET','POST'])
def datawhaleChart():
	# df = request backend dengan parameter ticker, interval, starTime, endTime. Sementara pakai data csv dulu
	# df = pd.read_csv("appDf.csv")
	# df request ke API Binance dulu sementara, nanti ke BigQuery
	ticker = None
	interval  = None
	startDateInput = None
	endDateInput = None
	userTimezone = None
	vwapPeriod = None
	maxAggTradesHourBatch = None
	
	if request.method == "POST":
		ticker = request.json["ticker"]
		interval  =request.json["interval"]
		if(request.json["startDate"]!=""):
			startDateInput = request.json["startDate"]
		if(request.json["endDate"]!=""):
			endDateInput = request.json["endDate"]
		userTimezone = int(request.json["userTimezone"])

	df = gd.getDatawhaleChart(ticker,interval,startDateInput,endDateInput,userTimezone,vwapPeriod,maxAggTradesHourBatch)
	
	ticker = ticker or "BTCUSDT"
	userTimezone = userTimezone or 0
	plot_json = pg.plotly_whaleChart(ticker, userTimezone, df)
	response = {"plot_json":plot_json}
	
	return response

if __name__ == '__main__':
	app.run(debug=True)