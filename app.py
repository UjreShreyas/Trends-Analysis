from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
import numpy as np
import random
from pytrends.request import TrendReq
import pandas as pd
import time

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Route to serve the main HTML file
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# Route to serve static files (CSS, JS)
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

def get_historical_trends(keyword, start_date, end_date):
    """Fetch historical trends data from Google Trends API"""
    try:
        # Initialize pytrends
        pytrends = TrendReq(hl='en-US', tz=360)
        
        # Build payload for the keyword
        pytrends.build_payload([keyword], cat=0, timeframe=f'{start_date} {end_date}', geo='', gprop='')
        
        # Get interest over time
        data = pytrends.interest_over_time()
        
        if data.empty or keyword not in data.columns:
            return [], []
        
        # Extract dates and interest values
        dates = [date.strftime('%Y-%m-%d') for date in data.index]
        interest = data[keyword].tolist()
        
        return dates, interest
        
    except Exception as e:
        print(f"Error fetching Google Trends data: {e}")
        return [], []

def generate_future_predictions(keyword, historical_data, start_date, end_date):
    """Generate future predictions based on historical trends"""
    prediction_dates = []
    predictions = []
    
    # Calculate the number of data points with smarter intervals
    total_days = (end_date - start_date).days
    total_years = total_days / 365.25

    if total_years <= 2:
        interval_days = 30  # Monthly for short ranges
    elif total_years <= 8:
        interval_days = 90  # Quarterly for medium ranges
    else:
        interval_days = 182  # Semi-annually for long ranges
    
    current_pred_date = start_date
    
    # Use historical data to inform predictions if available
    base_value = 50  # Default base value
    if historical_data:
        # Use the average of the last few historical points as baseline
        recent_data = historical_data[-min(12, len(historical_data)):]
        base_value = np.mean(recent_data)
    
    prediction_count = 0
    while current_pred_date <= end_date and prediction_count < 50:  # Limit predictions
        prediction_dates.append(current_pred_date.strftime('%Y-%m-%d'))
        
        days_from_start = (current_pred_date - start_date).days
        years_from_start = days_from_start / 365.25
        
        # Create prediction model based on keyword and historical trends
        if 'AI' in keyword.upper() or 'ARTIFICIAL INTELLIGENCE' in keyword.upper():
            # AI trend - exponential growth with eventual plateau
            growth_factor = 1.5 * (1 - np.exp(-years_from_start / 2))
            predicted_value = base_value * (1 + growth_factor)
        elif any(tech_word in keyword.upper() for tech_word in ['TECH', 'DIGITAL', 'CRYPTO', 'BLOCKCHAIN']):
            # Tech trends - cyclical with growth
            trend = base_value * (1 + 0.3 * years_from_start)
            cycle = 15 * np.sin(days_from_start * 2 * np.pi / 365.25)
            predicted_value = trend + cycle
        else:
            # General trends - moderate growth with seasonality
            trend = base_value * (1 + 0.1 * years_from_start)
            seasonal = 10 * np.sin(days_from_start * 2 * np.pi / 365.25)
            predicted_value = trend + seasonal
        
        # Add some randomness
        noise = random.uniform(-8, 8)
        predicted_value += noise
        
        # Keep within reasonable bounds
        predicted_value = max(5, min(100, predicted_value))
        predictions.append(round(predicted_value, 1))
        
        current_pred_date += timedelta(days=interval_days)
        prediction_count += 1
    
    return prediction_dates, predictions

# API endpoint for trend data with historical and predictions
@app.route('/get_trend_data', methods=['GET'])
def get_trend_data():
    keyword = request.args.get('keyword', 'Python programming')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    try:
        # Parse dates or use defaults
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        else:
            start_date = datetime.now() - timedelta(days=365*2)  # 2 years ago
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_date = datetime.now()
        
        # Ensure start date is not too far in the past (Google Trends limitation)
        earliest_date = datetime.now() - timedelta(days=365*5)  # 5 years max
        if start_date < earliest_date:
            start_date = earliest_date
            
        # Get historical data from Google Trends
        print(f"Fetching trends for '{keyword}' from {start_date.date()} to {end_date.date()}")
        dates, interest = get_historical_trends(keyword, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        
        # Generate future predictions (next 2 years from end_date)
        prediction_start = end_date + timedelta(days=1)
        prediction_end = prediction_start + timedelta(days=365*2)  # 2 years into future
        
        prediction_dates, predictions = generate_future_predictions(
            keyword, interest, prediction_start, prediction_end
        )
        
        # Calculate statistics
        all_values = interest + predictions
        max_interest = max(interest) if interest else 0
        avg_interest = round(np.mean(interest), 1) if interest else 0
        max_prediction = max(predictions) if predictions else 0
        avg_prediction = round(np.mean(predictions), 1) if predictions else 0
        
        # Find peak date
        peak_date = None
        if interest:
            peak_index = interest.index(max_interest)
            peak_date = dates[peak_index] if peak_index < len(dates) else dates[-1]
        
        # Determine trend direction
        trend_direction = 'Stable'
        if len(interest) > 1:
            if interest[-1] > interest[0]:
                trend_direction = 'Rising'
            elif interest[-1] < interest[0]:
                trend_direction = 'Declining'
        
        return jsonify({
            'keyword': keyword,
            'date': dates,
            'interest': interest,
            'prediction_dates': prediction_dates,
            'prediction': predictions,
            'max_interest': max_interest,
            'avg_interest': avg_interest,
            'max_prediction': max_prediction,
            'avg_prediction': avg_prediction,
            'peak_date': peak_date,
            'trend_direction': trend_direction,
            'data_points': len(dates),
            'prediction_points': len(prediction_dates)
        })
        
    except Exception as e:
        print(f"Error in get_trend_data: {e}")
        return jsonify({
            'error': 'Failed to fetch trend data',
            'message': str(e),
            'keyword': keyword,
            'date': [],
            'interest': [],
            'prediction_dates': [],
            'prediction': []
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
