from flask import Flask, render_template, request, send_file
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import folium
import os

app = Flask(__name__)

def get_location(query):
    geolocator = Nominatim(user_agent="my_map_application")
    try:
        location = geolocator.geocode(query, country_codes='us')  # Restrict search to the US
        if location is None:
            return None
        return location
    except GeocoderTimedOut:
        return None

def create_map_with_radius(query, radius_miles):
    location = get_location(query)
    if location is None:
        return None
    
    radius_meters = radius_miles * 1609.34
    my_map = folium.Map(location=[location.latitude, location.longitude], zoom_start=12)
    
    folium.Marker(
        [location.latitude, location.longitude],
        popup=location.address,
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(my_map)
    
    folium.Circle(
        radius=radius_meters,
        location=[location.latitude, location.longitude],
        popup=f'{radius_miles} mile radius',
        color='blue',
        fill=True,
        fill_color='blue'
    ).add_to(my_map)
    
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
        
        # Prioritize using zip code if provided
        location_query = zip_code if zip_code else city_state
        
        try:
            radius = float(radius)
            map_file = create_map_with_radius(location_query, radius)
            if map_file is None:
                error = "Could not find the specified location."
        except ValueError:
            error = "Please enter a valid number for the radius."
    return render_template('index.html', map_file=map_file, error=error)

if __name__ == '__main__':
    if not os.path.exists('static'):
        os.makedirs('static')
    app.run(debug=True)
