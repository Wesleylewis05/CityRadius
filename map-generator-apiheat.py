from flask import Flask, render_template, request, send_file
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import folium
import os
import requests
import json
from config import ORS_API_KEY  # Import API key from config.py

app = Flask(__name__)

def get_location(query):
    geolocator = Nominatim(user_agent="my_map_application")
    try:
        location = geolocator.geocode(query, country_codes='us')
        if location is None:
            return None
        return location
    except GeocoderTimedOut:
        return None

def get_isochrones(location, intervals_minutes):
    """Get isochrones from OpenRouteService API"""
    headers = {
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Authorization': ORS_API_KEY,
        'Content-Type': 'application/json; charset=utf-8'
    }
    
    body = {
        "locations": [[location.longitude, location.latitude]],
        "range": [interval * 60 for interval in intervals_minutes],  # Convert minutes to seconds
        "attributes": ["total_pop"],
        "location_type": "start",
        "range_type": "time",
        "area_units": "mi",
        "units": "mi"
    }

    url = 'https://api.openrouteservice.org/v2/isochrones/driving-car'
    
    try:
        response = requests.post(url, json=body, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling OpenRouteService API: {e}")
        return None

def create_map_with_isochrones(query, radius_miles):
    location = get_location(query)
    if location is None:
        return None
    
    # Create the base map
    my_map = folium.Map(location=[location.latitude, location.longitude], zoom_start=11)
    
    # Add the center marker
    folium.Marker(
        [location.latitude, location.longitude],
        popup=location.address,
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(my_map)
    
    # Time intervals for isochrones (in minutes)
    time_intervals = [10, 20, 30, 40, 50, 60]
    colors = ['green', 'yellow', 'orange', 'red', 'purple', 'black']
    
    # Get isochrones from ORS
    isochrones_data = get_isochrones(location, time_intervals)
    
    if isochrones_data and 'features' in isochrones_data:
        # Add isochrones to map (in reverse order so smaller times are on top)
        for feature, color in zip(reversed(isochrones_data['features']), reversed(colors)):
            time_minutes = feature['properties']['value'] / 60  # Convert seconds to minutes
            folium.GeoJson(
                feature,
                style_function=lambda x, color=color: {
                    'fillColor': color,
                    'color': color,
                    'weight': 2,
                    'fillOpacity': 0.3
                },
                tooltip=f'{int(time_minutes)} min drive time'
            ).add_to(my_map)
    
        # Add a visual radius circle for reference
        radius_meters = radius_miles * 1609.34
        folium.Circle(
            radius=radius_meters,
            location=[location.latitude, location.longitude],
            popup=f'{radius_miles} mile radius',
            color='black',
            weight=2,
            fill=False,
            dash_array='10'
        ).add_to(my_map)
    
    # Add an improved legend
    legend_html = '''
    <div style="
        position: fixed;
        bottom: 50px;
        left: 50px;
        width: 200px;
        background-color: white;
        border: 2px solid grey;
        border-radius: 6px;
        z-index: 9999;
        padding: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    ">
        <h4 style="margin-bottom: 10px; border-bottom: 1px solid #ccc; padding-bottom: 5px;">
            Drive Time (minutes)
        </h4>
        <div style="margin: 5px 0;">
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="width: 20px; height: 20px; background: green; opacity: 0.3; border: 2px solid green; margin-right: 10px;"></div>
                <span>0-10</span>
            </div>
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="width: 20px; height: 20px; background: yellow; opacity: 0.3; border: 2px solid yellow; margin-right: 10px;"></div>
                <span>10-20</span>
            </div>
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="width: 20px; height: 20px; background: orange; opacity: 0.3; border: 2px solid orange; margin-right: 10px;"></div>
                <span>20-30</span>
            </div>
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="width: 20px; height: 20px; background: red; opacity: 0.3; border: 2px solid red; margin-right: 10px;"></div>
                <span>30-40</span>
            </div>
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="width: 20px; height: 20px; background: purple; opacity: 0.3; border: 2px solid purple; margin-right: 10px;"></div>
                <span>40-50</span>
            </div>
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="width: 20px; height: 20px; background: black; opacity: 0.3; border: 2px solid black; margin-right: 10px;"></div>
                <span>50-60</span>
            </div>
        </div>
        <div style="margin-top: 10px; border-top: 1px solid #ccc; padding-top: 5px;">
            <div style="display: flex; align-items: center;">
                <div style="width: 20px; height: 2px; border-top: 2px dashed black; margin-right: 10px;"></div>
                <span>Distance radius</span>
            </div>
        </div>
    </div>
    '''
    my_map.get_root().html.add_child(folium.Element(legend_html))
    
    output_file = 'static/city_map_with_radius.html'
    my_map.save(output_file)
    return output_file

@app.route('/', methods=['GET', 'POST'])
def index():
    map_file = None
    error = None
    if request.method == 'POST':
        city_state = request.form.get('city_state')
        zip_code = request.form.get('zip_code')
        radius = request.form.get('radius')
        
        location_query = zip_code if zip_code else city_state
        
        try:
            radius = float(radius)
            map_file = create_map_with_isochrones(location_query, radius)
            if map_file is None:
                error = "Could not find the specified location or error getting drive times."
        except ValueError:
            error = "Please enter a valid number for the radius."
    return render_template('index.html', map_file=map_file, error=error)

if __name__ == '__main__':
    if not os.path.exists('static'):
        os.makedirs('static')
    app.run(debug=True)