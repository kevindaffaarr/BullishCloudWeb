from pandas.core.indexes import interval
import requests
import json
import datetime as dt
import pandas as pd
# ==================================================================================================================
# FUNCTION
# ==================================================================================================================
def resampler_with_threshold(df):
	threshold95 = df["q"].quantile(0.95)
	df = df[(df.q >= threshold95)].sum()
	return df

def intervalToIntervalM (interval):
	switcher = {
		"1m":1, 
		"5m":5, 
		"15m":15, 
		"30m":30, 
		"1h":60, 
		"4h":240, 
		"1D":1440
	}
	return switcher.get(interval,"Invalid Interval")

def floorTimestamp(timestamp,intervalM):
	return timestamp - (timestamp%intervalM)

# ==================================================================================================================
# getData
# ==================================================================================================================
def getDatawhaleChart(ticker="BTCUSDT",interval="1m", 
							startDateInput=(dt.datetime.utcnow()-dt.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M"), 
							endDateInput="realtime",userTimezone=0, 
							vwapPeriod=21,maxAggTradesHourBatch=6):
	
	# ==================================================================================================================
	# INPUT ADJUSTMENT
	# ==================================================================================================================
	ticker = ticker or "BTCUSDT"
	interval = interval or "1m"
	intervalM = intervalToIntervalM(interval)
	endDateInput = endDateInput or "realtime" # choose: 2021-05-14 03:00:00 || realtime
	if(startDateInput):
		startDateInput = dt.datetime.strptime(startDateInput, "%Y-%m-%dT%H:%M")-dt.timedelta(hours=userTimezone)
	elif(endDateInput!="realtime"):
		startDateInput = (dt.datetime.strptime(endDateInput, "%Y-%m-%dT%H:%M")-dt.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
	else:
		startDateInput = (dt.datetime.utcnow()-dt.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
	userTimezone = userTimezone or 0
	vwapPeriod = vwapPeriod or 21
	maxAggTradesHourBatch = maxAggTradesHourBatch or 6 # for memory usage control

	# ==================================================================================================================
	# SCRIPTS DATA PREP
	# ==================================================================================================================
	# INITIATE VARIABLE
	klines = pd.DataFrame()
	whaleTrade = pd.DataFrame()
	whaleSummary = pd.DataFrame()

	# TIME BOUNDS CONFIG
	startDate = startDateInput
	if endDateInput == "realtime":
		endDate = dt.datetime.utcnow() #serverTime UTC
	else:
		endDate = dt.datetime.strptime(endDateInput, "%Y-%m-%dT%H:%M") - dt.timedelta(hours=userTimezone) + dt.timedelta(minutes=1)

	startDate = startDate.replace(tzinfo=dt.timezone.utc)
	endDate = endDate.replace(tzinfo=dt.timezone.utc)

	startTime = floorTimestamp(startDate.timestamp()*1000,intervalM)
	endDate = endDate.timestamp()*1000

	# ==================================================================================================================
	# QUERY DATA AGGTRADES DAN KLINES
	# BATAS ATAS QUERY
	# Next dari BigQuery
	# ==================================================================================================================
	
	# REQUEST AGGTRADES
	AggTradesHourBatch = 0
	while (startTime <= endDate):
		while (startTime <= endDate and AggTradesHourBatch < maxAggTradesHourBatch):
			endTime = min(startTime + 60*60*1000, endDate)

			base = "https://api.binance.com"
			get_url = "/api/v3/aggTrades"
			params_url = "symbol="+ticker+"&startTime="+str(int(startTime))+"&endTime="+str((int(endTime)))
			url = base + get_url + '?' + params_url

			response = requests.get(url).text
			if response != "[]":
				df = pd.DataFrame(json.loads(response))
				del response
				# df.columns=columns=["a","p","q","f","l","T","m","M"]
				df["q"] = pd.to_numeric(df["q"])
				df["p"] = pd.to_numeric(df["p"])
				df["v"] = df["q"]*df["p"]
				df = df.drop(columns=["a","p","f","l","M",])
			else:
				df = pd.DataFrame({"T":[startTime]})

			whaleTrade = whaleTrade.append(df,ignore_index = True)
			del df

			print(dt.datetime.utcfromtimestamp(startTime/1000) + dt.timedelta(hours=userTimezone))
			
			if endDateInput =="realtime":
				url = "https://api.binance.com/api/v3/time"
				data = json.loads(requests.get(url).text)
				serverTime = data["serverTime"]
				endDate = serverTime
			startTime = startTime + 60*60*1000
			AggTradesHourBatch = AggTradesHourBatch + 1

		print("resampling...")
		# whaleSummary PREP
		whaleTrade.columns=columns=["q","OpenTime","m","v"]
		whaleTrade = whaleTrade.assign(OpenTime=lambda x: pd.to_datetime(x.OpenTime, unit="ms"))
		whaleTrade = whaleTrade.set_index("OpenTime")

		resamplePeriod = str(intervalM)+"T"
		tradeTrue = whaleTrade[(whaleTrade.m ==True)].resample(resamplePeriod).apply(resampler_with_threshold)
		tradeFalse = whaleTrade[(whaleTrade.m ==False)].resample(resamplePeriod).apply(resampler_with_threshold)
		del whaleTrade
		
		tradeTrue.columns=columns=["qTrue","mTrue","vTrue"]
		tradeFalse.columns=columns=["qFalse","mFalse","vFalse"]

		whaleTrade = pd.concat([tradeTrue, tradeFalse], axis=1)
		del tradeTrue
		del tradeFalse

		whaleTrade["netVol"] = whaleTrade["qFalse"] - whaleTrade["qTrue"]
		whaleTrade = whaleTrade.drop(columns=["qTrue","mTrue","vTrue","mFalse",])

		whaleTrade.reset_index(inplace=True)
		whaleTrade = whaleTrade.rename(columns = {'index':'OpenTime'})
		whaleTrade["OpenTime"] = whaleTrade["OpenTime"].apply(lambda x: int(x.timestamp()*1000))

		df = pd.DataFrame({"timeStamps":whaleTrade["OpenTime"], 
							"buyVol":whaleTrade["qFalse"],"buyVal":whaleTrade["vFalse"], 
							"netVol":whaleTrade["netVol"]})

		whaleSummary = whaleSummary.append(df,ignore_index = True)
		del df
		
		whaleTrade = pd.DataFrame()
		AggTradesHourBatch = 0

	# whaleSummary["cumVol"] = whaleSummary["netVol"].cumsum()
	whaleSummary["VWAPBuyer"] = whaleSummary["buyVal"].rolling(window=vwapPeriod).sum()/whaleSummary["buyVol"].rolling(window=vwapPeriod).sum()
	whaleSummary = whaleSummary.drop(["buyVal","buyVol"], axis=1)

	# REQUEST KLINES
	url = "https://api.binance.com/api/v3/time"
	data = json.loads(requests.get(url).text)
	serverTime = data["serverTime"]
	if endDateInput =="realtime":
		endDate = serverTime
	startTime = startDate.timestamp()*1000
	endTime = endDate

	nData = (endTime-startTime)/1000/(intervalM*60) + 1
	klinesBatch = 0
	
	while(nData-klinesBatch*1000 > 0 and startTime <= endDate):
		endTime = int(min(startTime + (1*1000*intervalM*60*1000), endDate))

		base = "https://api.binance.com"
		get_url = "/api/v3/klines"
		params_url = "symbol="+ticker+"&interval="+str(interval)+"&startTime="+str(int(startTime))+"&endTime="+str((int(endTime)))+"&limit=1000"
		url = base + get_url + '?' + params_url
		df = pd.DataFrame(json.loads(requests.get(url).text))
		# klines.columns=columns=["OpenTime","Open","High","Low","Close","Volume","CloseTime","QuoteAssetVolume","NumberOfTrades","TakerBuyBaseAssetVolume","TakerBuyQuoteAssetVolume","Ignore"]
		df = df.drop([6,7,9,10,11], axis=1)
		df = df.apply(pd.to_numeric)
		klines = klines.append(df,ignore_index = True)
		startTime = startTime + (1*1000*intervalM*60*1000)
		klinesBatch = klinesBatch + 1

	# KLINES PREP
	# Rename column klines
	klines.columns=columns=["OpenTime","Open","High","Low","Close","Volume","NumberOfTrades"]
	# Handle missing price
	klines[["Open","High","Low","Close","Volume","NumberOfTrades"]] = klines[["Open","High","Low","Close","Volume","NumberOfTrades"]].fillna(method="ffill")

	# MERGE KLINES + WHALESUMMARY
	priceWhaleData = klines.merge(whaleSummary, how="right", left_on="OpenTime", right_on="timeStamps")
	
	# ==================================================================================================================
	# BATAS BAWAH QUERY
	# Next dari BigQuery. Perlu diubah. Return script BigQuery harus sama dengan priceWhaleData
	# ==================================================================================================================
	
	priceWhaleData["netVol"] = priceWhaleData["netVol"]/priceWhaleData["Volume"]
	priceWhaleData["cumVol"] = priceWhaleData["netVol"].cumsum()

	# ==================================================================================================================
	# RETURN
	# ==================================================================================================================
	return priceWhaleData