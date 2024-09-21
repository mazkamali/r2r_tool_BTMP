import ipyleaflet
from ipyleaflet import Map, GeoJSON, Marker, Popup, WidgetControl
import shinywidgets
from shinywidgets import render_widget, output_widget
import pandas as pd
from shiny import reactive, req, App, ui, render
import geopandas as gpd
import plotly.express as px
from ipywidgets import Layout, HTML
import matplotlib.cm as cm
import matplotlib.colors as colors
import json
import os


# Get the current script directory
script_dir = os.path.dirname(__file__)

# Path to the shapefile
shapefile_path = os.path.join(script_dir, 'data', 'R2R_N_sgmnt_ID_v8.shp')

# Path to the second external file (excel)
excel_path = os.path.join(script_dir, 'data', '67985_BTMP_Network_Designation_Final_Scoring_100mile.xlsx')


# load segment data
df = pd.read_excel(excel_path)


# Read the shapefile (replace 'path_to_your_shapefile.shp' with your actual shapefile path)
# shapefile_path = "C:/Users/mkamali/PycharmProjects/Python Projects/PyShiny/data/R2R_N_sgmnt_ID_v8.shp"
gdf = gpd.read_file(shapefile_path).to_crs("EPSG:4326")


# add segment data
gdf = gdf.merge(df, on="RIA_FRM_TO")

# Function to create a color scale
def get_color(value, vmin, vmax):
    norm = colors.Normalize(vmin=vmin, vmax=vmax)
    cmap = cm.get_cmap('Blues')  # Use a color map, e.g., 'coolwarm'
    rgba = cmap(norm(value))
    return colors.rgb2hex(rgba[:3])  # Convert RGBA to hex color




def create_map(selected_nd_metric):
    # Get the centroid of the shapefile's geometry to center the map
    centroid = gdf.geometry.centroid.unary_union.centroid
    
    # Create a base map centered on the shapefile's centroid
    m = Map(center=(centroid.y, centroid.x), zoom=7, layout=Layout(width='80%', height='800px'), scroll_wheel_zoom = True, close_popup_on_click=False)  

    # Extract numerical attributes to compute min and max for color scaling
    gjson_data = gdf.to_json()
    gjson_data = json.loads(gjson_data)
    nd_metric_values = [feature['properties'].get(selected_nd_metric, 0) for feature in gjson_data['features']]
    vmin, vmax = min(nd_metric_values), max(nd_metric_values)

    # Assign colors to each feature based on the numerical attribute
    for feature in gjson_data['features']:
        value = feature['properties'].get(selected_nd_metric, 0)
        feature['properties']['style'] = {
            'color': get_color(value, vmin, vmax),
            'weight': 5,
            'opacity': 0.7
        }

    # Create GeoJSON layer from the shapefile's GeoJSON data
    # geo_json = GeoJSON(data=gdf.__geo_interface__) 
    geo_json = GeoJSON(data=gjson_data)

    # Define a dictionary to map attribute names to human-readable labels
    attribute_labels = {
        "FINAL_score": "Final Score",
        "Pe_G_M_S_y": "People and Goods Movement Score",
        "Mak_Acc_S_y": "Market Access Score"
    }

    
    # Function to handle feature clicks and display a popup
    def on_click(event, feature, **kwargs):
        # Extract the name and population from the feature properties
        name = feature['properties']['Corridor_j']
        value = round(feature['properties'].get(selected_nd_metric, 0),1)

        # Get the middle coordinate of the line to display the popup
        coordinates = feature['geometry']['coordinates']
        midpoint = coordinates[len(coordinates) // 2]  # Get the middle point of the line

        # Use the human-readable label for the selected attribute
        label = attribute_labels.get(selected_nd_metric, selected_nd_metric)
        
        # Create an HTML popup content
        popup_content = HTML()
        popup_content.value = f"Corridor: <b>{name}</b><br>{label}: {value}"

        # add location to the popup
        popup = Popup(location=[midpoint[1], midpoint[0]], child=popup_content)
        
        m.add_layer(popup)

    # Attach the click handler to the GeoJSON layer
    geo_json.on_click(on_click)


    # Add the GeoJSON layer to the map
    m.add_layer(geo_json)

    # Add a color scale legend to the map

    legend_html = f"""
    <div style="
        position: fixed;
        bottom: 20px; left: 20px; width: 300px; height: 100px;
        background-color: white; border:2px solid grey; z-index:9999; font-size:14px;
        padding: 10px; border-radius: 5px;
    ">
    <b>{attribute_labels[selected_nd_metric]}</b><br>
    Min Score: <i style="background:{get_color(vmin, vmin, vmax)};width:20px;height:10px;display:inline-block;"></i> {round(vmin, 1)}<br>
    Max Score: <i style="background:{get_color(vmax, vmin, vmax)};width:20px;height:10px;display:inline-block;"></i> {round(vmax, 1)}
    </div>
    """
    legend = HTML(value=legend_html)
    legend_control = WidgetControl(widget=legend, position="bottomright")
    m.add_control(legend_control)

    # Return the map as a widget to be displayed in the Shiny app
    return m



# ui of the app
app_ui = ui.page_fluid(
    ui.h2("R2R Needs Assessment Tool"),

    # drop down to select a needs metric
    ui.input_select(  
        "nd_metric",  
        "Select a Needs Metric Below:",  
        {"FINAL_score": "Final Score", "Pe_G_M_S_y": "People and Goods Movement Score", "Mak_Acc_S_y": "Market Access Score"},  
    ),

    # Add five input sliders for percentages
    ui.input_slider("slider1", "Slider 1", min=0, max=100, value=20),
    ui.input_slider("slider2", "Slider 2", min=0, max=100, value=20),
    ui.input_slider("slider3", "Slider 3", min=0, max=100, value=20),
    ui.input_slider("slider4", "Slider 4", min=0, max=100, value=20),
    ui.input_slider("slider5", "Slider 5", min=0, max=100, value=20),

    # add the map 
    output_widget("map_output")
)

# Step 5: Define Server Logic
def server(input, output, session):

    # input metric weight logic
    @reactive.Effect
    def adjust_sliders():
        sliders = [
            input.slider1(),
            input.slider2(),
            input.slider3(),
            input.slider4(),
            input.slider5(),
        ]
        total = sum(sliders)

        # Ensure the total remains 100 by proportionally adjusting the sliders
        if total != 100:
            ratio = 100 / total
            ui.update_slider("slider1", value=int(input.slider1() * ratio))
            ui.update_slider("slider2", value=int(input.slider2() * ratio))
            ui.update_slider("slider3", value=int(input.slider3() * ratio))
            ui.update_slider("slider4", value=int(input.slider4() * ratio))
            ui.update_slider("slider5", value=int(input.slider5() * ratio))




    # map logic
    @output
    @render_widget
    def map_output():
         selected_nd_metric = input.nd_metric()
         print(selected_nd_metric)
         return create_map(selected_nd_metric)
    
    

# Create and Run the Shiny App
app = App(app_ui, server)