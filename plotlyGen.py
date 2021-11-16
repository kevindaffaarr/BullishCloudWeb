import plotly
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import numpy as np
import json

from datetime import datetime, timedelta

import pandas as pd

def plotly_whaleChart(ticker, userTimezone, df):
	# Asumsi data kolom Open Time dari backend masih timestamp. Lebih baik timestamp UTC sehingga mudah untuk menyesuaikan ke userTimezone
	df = df.assign(OpenTime=lambda x: pd.to_datetime(x.OpenTime, unit="ms")+timedelta(hours=userTimezone))

	# MAKE_SUBPLOTS
	fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
						specs=[[{"secondary_y":True}], 
							   [{"secondary_y":True}]], 
						vertical_spacing=0, 
						row_heights=[0.7,0.3])

	# ADD_TRACE
	fig.add_trace(go.Candlestick(x=df["OpenTime"], 
								open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Price"), 
					row=1, col=1, secondary_y=True
	)

	fig.add_trace(go.Scatter(x=df["OpenTime"], y=df["VWAPBuyer"], name="VWAPBuyer", 
							marker_color="orange"), 
					row=1, col=1, secondary_y=True
	)

	fig.add_trace(go.Scatter(x=df["OpenTime"], y=df["cumVol"], name="Volume Flow", 
							marker_color="blue"), 
					row=1, col=1, secondary_y=False
	)

	fig.add_trace(go.Bar(x=df["OpenTime"], y=df["netVol"], 
						marker_color=np.where(df["netVol"] < 0, 'red', 'green'),name="Net Volume"), 
					row=2, col=1
	)

	# UPDATE_AXES
	fig.update_yaxes(title_text="Price", row=1, col=1, secondary_y=True)
	fig.update_yaxes(title_text="Net Vol", row=2, col=1)
	fig.update_yaxes(showgrid=False, row=1, col=1,secondary_y=False)
	fig.update_xaxes(title_text="Open Time", row=2, col=1)
	fig.update_xaxes(rangeslider={"autorange":True, "visible":False})
	
	# UPDATE_LAYOUT
	TICKER = ticker.upper()
	fig.update_layout(title={"text":TICKER, "x":0.5})
	fig.update_layout(legend={"orientation":"h","y":-0.2})
	
	# UPDATE_LAYOUT DEFAULT. Copy to all charts
	fig.update_layout(template="plotly_white")
	fig.update_layout(dragmode="pan")
	fig.update_layout(margin=dict(l=0,r=0,b=0,t=50,pad=0))
	
	plot_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
	return plot_json