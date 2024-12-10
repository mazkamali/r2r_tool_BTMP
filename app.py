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
import numpy as np


# Get the current script directory
script_dir = os.path.dirname(__file__)


# Function to create a color scale
def get_color(value, vmin, vmax):

    if value <= vmin:
        return "green"
    elif vmin < value <= vmax:
        return "yellow"
    else:
        return "red"
    # norm = colors.Normalize(vmin=vmin, vmax=vmax)
    # cmap = cm.get_cmap('coolwarm')  # Use a color map, e.g., 'coolwarm'
    # rgba = cmap(norm(value))
    # #rgba = cmap(value)
    # return colors.rgb2hex(rgba[:3])  # Convert RGBA to hex color


def create_map(selected_nd_metric, gdf):

    # Get the centroid of the shapefile's geometry to center the map
    centroid = gdf.geometry.centroid.unary_union.centroid
    
    # Create a base map centered on the shapefile's centroid
    m = Map(center=(centroid.y, centroid.x), zoom=7, layout=Layout(width='80%', height='800px'), scroll_wheel_zoom = True, close_popup_on_click=False)  

    # Extract numerical attributes to compute min and max for color scaling
    gjson_data = gdf.to_json()
    gjson_data = json.loads(gjson_data)
    nd_metric_values = [feature['properties'].get(selected_nd_metric, 0) for feature in gjson_data['features']]
    tertiles = [np.quantile(nd_metric_values, 0.33), np.quantile(nd_metric_values, 0.66)]
    #vmin, vmax = min(nd_metric_values), max(nd_metric_values)
    vmin, vmax = tertiles[0], tertiles[1]

    # Assign colors to each feature based on the numerical attribute
    for feature in gjson_data['features']:
        value = feature['properties'].get(selected_nd_metric, 0)
        feature['properties']['style'] = {
            'color': get_color(value, vmin, vmax),
            'weight': 5,
            'opacity': 0.8
        }

    # Create GeoJSON layer from the shapefile's GeoJSON data
    # geo_json = GeoJSON(data=gdf.__geo_interface__) 
    geo_json = GeoJSON(data=gjson_data)

    # Define a dictionary to map attribute names to human-readable labels
    attribute_labels = {
        "final_score": "Final Score",
        "mob_rel_con_score": "Mobility, Reliability, & Connectivity",
        "safe_sec_score": "Safety and Security",
        "asst_pres_tech_score" : "Asset Preservation and Technology",
        "cust_stew_sust_eq_score" : "Customer Service, Stewardship, Sustainability, & Equity"
    }

    
    # Function to handle feature clicks and display a popup
    def on_click(event, feature, **kwargs):
        # Extract the name and population from the feature properties
        name = feature['properties']['Corridor_j']
        value = round(feature['properties'].get(selected_nd_metric, 0),1)

        # Get the middle coordinate of the line to display the popup
        coordinates = feature['geometry']['coordinates']
        
        if(isinstance(coordinates[0][0], list)):
            midpoint = coordinates[1][len(coordinates[1]) // 2]  # Get the middle point of the line
        else:
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

    ui.row(

        # input boxes for weights

        ui.column(3,ui.input_numeric("mob_w","Mobility, Reliability, and Connectivity",25, min = 0, max = 100)),
        ui.column(2,ui.input_numeric("safety_w","Safety and Security", 25, min = 0, max = 100)),
        ui.column(4,ui.input_numeric("asset_w","Asset Preservation and Technology Deployment", 25, min = 0, max = 100)),
        ui.column(3,ui.input_numeric("cust_w","Customer Service and Equity", 25, min = 0, max = 100))
    ),#end of ui row


    # warning message for when sum of inputs > 100
    ui.row(
        ui.div(

            ui.output_text("warning_msg"),
            style="color: red; font-weight: bold;"
        ) 
    ),

    # drop down to select a needs metric
    ui.input_select(  
        "nd_metric",  
        "Select a Needs Metric Below:",  
        {"final_score": "Final Score",
        "mob_rel_con_score": "Mobility, Reliability, & Connectivity",
        "safe_sec_score": "Safety and Security",
        "asst_pres_tech_score" : "Asset Preservation and Technology",
        "cust_stew_sust_eq_score" : "Customer Service, Stewardship, Sustainability, & Equity"},  
    ),


    # add the map 
    output_widget("map_output")
)

# Step 5: Define Server Logic
def server(input, output, session):

    # map logic
    @output
    @render_widget
    def map_output():
         selected_nd_metric = input.nd_metric()
         gdf = compute_weighted_final_score()
         return create_map(selected_nd_metric, gdf)


    # warning message logic
    @output
    @render.text
    def warning_msg():
        # Show a warning if the input is greater than 100
        weight_vals = [input.mob_w(), input.safety_w(), input.asset_w(), input.cust_w()]
        if sum(weight_vals) > 100:
            return "Warning: Sum of weights exceeds 100!"
        elif sum(weight_vals) < 100:
            return "Warning: Sum of weights is less than 100!"   
        else:
            return "" # No warning if condition is not met
    
    
    # read date logic
    @reactive.Calc
    def read_data():
        # Path to the second external file (excel)
        excel_path = os.path.join(script_dir, 'data', 'Needs Assessment Criteria_Scores.xlsx')

        # load corridor data
        df = pd.read_excel(excel_path, sheet_name = "data_MAPPING")

        # Path to the shapefile
        shapefile_path = os.path.join(script_dir, 'data', 'R2R_N_corridors_Final_v2.shp')


        # Read the shapefile (replace 'path_to_your_shapefile.shp' with your actual shapefile path)
        gdf = gpd.read_file(shapefile_path).to_crs("EPSG:4326")


        # add corridor data
        gdf = gdf.merge(df, on="Corridor_j")

        return gdf


    # Weighting logic
    @reactive.Calc
    def compute_weighted_final_score():
        gdf = read_data()
        gdf['final_score'] = gdf['mob_rel_con_score'] * (input.mob_w()/100) + gdf['safe_sec_score'] * (input.safety_w()/100) + gdf['asst_pres_tech_score'] * (input.asset_w()/100) + gdf['cust_stew_sust_eq_score'] * (input.cust_w()/100)
        return gdf




# Create and Run the Shiny App
app = App(app_ui, server)