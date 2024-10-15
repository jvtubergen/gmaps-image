# Google Maps retrieval functionality
from PIL import Image
import numpy as np
import math
import os
import requests


cos  = math.cos
sec  = lambda phi: 1/cos(phi) # Secant
sin  = math.sin
tan  = math.tan
asin = math.asin
atan = math.atan
acos = math.acos
sinh = math.sinh
exp  = math.exp
log  = math.log
pow  = math.pow
pi   = math.pi
sqrt = math.sqrt
ceil = math.ceil
floor= math.floor

earth_radius = 6378137 # meters
earth_circumference = 2*pi*earth_radius

cache_folder = os.path.expanduser("~/.cache/gmaps-image/")

# Gudermann function. Real argument abs(rho) < 0.5*pi 
# https://en.wikipedia.org/wiki/Gudermannian_function
def gd(tau):
    return 2 * atan(exp(tau)) - 0.5 * pi
def gd_inv(rho):
    return log(sec(rho) + tan(rho))


# Conversion between radians and degrees (for readability).
def rad_to_deg(phi):
    return phi * 180 / pi
def deg_to_rad(rho):
    return rho * pi / 180


# Maximal latitude (of web mercator projection).
# https://en.wikipedia.org/wiki/Mercator_projection
max_lat = rad_to_deg(gd(pi)) # = atan(sinh(pi)) / pi * 180


# Read image file as numpy array.
def read_image(filename):
    image = Image.open(filename)
    image = image.convert("RGB")
    image = np.array(image)
    return image


# Write numpy array with size (width, height, RGB) as an image file.
def write_image(image, filename):
    Image.fromarray(image).save(filename) 


# Cut out pixels of image at borders.
def cut_logo(image, scale, margin):
    off = scale * margin
    return image[off:-off,off:-off,:]


# Build filename and url for image.
def build_filename_and_url(lat, lon, zoom, resolution, scale, api_key):
    filename = "image_lat=%.6f_lon=%.6f_zoom=%d_scale=%d_size=%d.png" % (lat, lon, zoom, scale, resolution)
    url = "https://maps.googleapis.com/maps/api/staticmap?center="+("%.6f" % lat)+","+("%.6f" % lon)+"&zoom="+str(int(zoom))+"&scale="+str(int(scale))+"&size="+str(int(resolution))+"x"+str(int(resolution))+"&maptype=satellite&style=element:labels|visibility:off&key=" + api_key
    return filename, url


def fetch_image(lat, lon, zoom, resolution, scale, api_key):
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        # response.status_code
    except HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")
    else:
        print("Success!")
    
    type(response.content) # <class 'bytes'>
    response.encoding # 
    # somehow interpret as png..?

    return response.content
    

# Fetch url and store under fname.
def fetch_url(fname, url, *params): # params is a list of [("query", "value")] pairs
    try:
        response = requests.get(url, params, timeout=5)
        response.raise_for_status()

        with open(fname, 'wb') as file:
            file.write(response.content)

        return True

    except Exception as e:
        print(e)

        return False


# Uniform web mercator projection
# y,x in [0,1], starting in upper-left corner (thus lat 85 and lon -180)
# lat in [-85, 85], lon in [-180, 180]
def latlon_to_webmercator_uniform(lat, lon):
    x = 0.5 + deg_to_rad(lon) / (2*pi)
    y = 0.5 - gd_inv(deg_to_rad(lat)) / (2*pi)
    return y, x
def webmercator_uniform_to_latlon(y, x):
    lon = rad_to_deg(2*pi * (x - 0.5))
    lat = rad_to_deg(gd(2*pi * (0.5 - y)))
    return lat, lon


# Conversion between latlon and world/tile/pixelcoordinates.
# Tile and pixel coordinates depends on zoom level.
# In general, the uniform webmercator y,x values are scaled.
def pixelcoord_to_latlon(y, x, zoom):
    pixelcount = int(256 * pow(2, zoom))
    return webmercator_uniform_to_latlon(y / pixelcount, x / pixelcount)
def latlon_to_pixelcoord(lat, lon, zoom):
    y, x = latlon_to_webmercator_uniform(lat, lon)
    pixelcount = int(256 * pow(2, zoom))
    return int(y * pixelcount), int(x * pixelcount)
def latlon_to_tilecoord(lat, lon, zoom):
    y, x = latlon_to_webmercator_uniform(lat, lon)
    tilecount = int(pow(2, zoom))
    return int(y * tilecount), int(x * tilecount)
def latlon_to_worldcoord(lat, lon):
    y, x = latlon_to_webmercator_uniform(lat, lon)
    return y * 256, x * 256


# GSD (Ground Sampling Distance): spatial resolution (in meters) of the image.
def compute_gsd(lat, zoom, scale):
    k = sec(deg_to_rad(lat)) # Scale factor by mercator projection.
    w = earth_circumference  # Total image distance on 256x256 world image
    return w / (256 * pow(2, zoom) * k * scale)


# Compute zoom in such that related GSD is smaller or equal to the goal GSD.
def derive_zoom(lat, scale, goal_gsd, deviation=0.0):

    k = sec(deg_to_rad(lat)) # Scale factor by mercator projection.
    w = earth_circumference  # Total image distance on 256x256 world image
    # gsd = w / (256 * pow(2, zoom) * k * scale)
    # w / gsd = 256 * pow(2, zoom) * k * scale
    # w / (256 * gsd) = pow(2, zoom) * k * scale
    # w / (256 * gsd * k * scale) = pow(2, zoom)
    zoom = log(w / (256 * goal_gsd * k * scale), 2)

    zoom1 = floor(zoom)
    zoom2 = ceil(zoom)

    gsd1 = compute_gsd(lat, zoom1, scale) 
    gsd2 = compute_gsd(lat, zoom2, scale) 

    if gsd1 <= goal_gsd + deviation:
        return zoom1
    else:
        assert gsd2 <= goal_gsd + deviation
        return zoom2


# Adapt coordinates into a square.
# * Assumes uniform horizonal and vertical distance (thus don't apply to mercurator coordinates).
# * Assume to be inclusive (thus increasing area size rather than lowering it).
def squarify_coordinates(p1, p2):
    y1, x1 = p1
    y2, x2 = p2
    w = x2 - x1
    h = y2 - y1
    if h > w:
        diff = h - w
        left = floor(0.5 * diff)
        right= ceil(0.5 * diff)
        x1 = x1 - left
        x2 = x2 + right
    if w > h:
        diff = w - h
        above= floor(0.5 * diff)
        below= ceil(0.5 * diff)
        y1 = y1 - above
        y2 = y2 + below
    return [y1, x1], [y2, x2]


# Squarify, but in terms of meb mercator coordinates.
# Note the difference, scaling is inhomogeneous.
def squarify_web_mercator_coordinates(p1, p2, zoom):
    # Convert web mercator coordinates into pixel coordinates.
    # Deconstruct latlons.
    lat1, lon1 = p1 # Upper-left  corner (thus higher latitude and lower longitude).
    lat2, lon2 = p2 # Lower-right corner (thus lower latitude and higher longitude).

    # Obtain pixel range in google maps at given zoom.
    y1, x1 = latlon_to_pixelcoord(lat1, lon1, zoom)
    y2, x2 = latlon_to_pixelcoord(lat2, lon2, zoom)

    # Squarify the result.
    p1, p2 = [y1, x1], [y2, x2]
    p1, p2 = squarify_coordinates(p1, p2)
    [y1, x1], [y2, x2] = p1, p2

    # Return to web mercator coordinates.
    lat1, lon1 = pixelcoord_to_latlon(y1, x1, zoom)
    lat2, lon2 = pixelcoord_to_latlon(y2, x2, zoom)

    p1 = lat1, lon1
    p2 = lat2, lon2

    return p1, p2


# Retrieve images, stitch them together.
# * Adjust to have tile consistency, this should reduce the number of requests we are making.
# * Prefer higher scale, lowers image retrieval count as well.
def construct_image(north=None, west=None, east=None, south=None, zoom=None, scale=None, api_key=None, full_tiles=False, square=False):
    
    assert north   != None
    assert west    != None
    assert east    != None
    assert south   != None
    assert zoom    != None
    assert scale   != None
    assert api_key != None

    # Deconstruct latlons.
    lat1, lon1 = north, west # Upper-left  corner (thus higher latitude and lower longitude).
    lat2, lon2 = south, east # Lower-right corner (thus lower latitude and higher longitude).

    # Obtain pixel range in google maps at given zoom.
    y1, x1 = latlon_to_pixelcoord(lat1, lon1, zoom)
    y2, x2 = latlon_to_pixelcoord(lat2, lon2, zoom)

    if square:
        p1, p2 = [y1, x1], [y2, x2]
        p1, p2 = squarify_coordinates(p1, p2)
        [y1, x1], [y2, x2] = p1, p2

    max_resolution = 640 # Google Maps images up to 640x640.
    margin = 22 # Necessary to cut out logo.

    # Construct tiles (to fetch).
    step = max_resolution - 2*margin # Tile step size.
    t1 = (y1 // step, x1 // step) # Tile in which upper-left  pixel lives.
    t2 = (y2 // step, x2 // step) # Tile in which lower-right pixel lives.
    tiles = [(j, i) for j in range(t1[0],t2[0] + 1) for i in range(t1[1],t2[1] + 1)]
    width  = len(range(t1[1],t2[1] + 1)) # Tile width.
    height = len(range(t1[0],t2[0] + 1)) # Tile height.

    # Convert tiles into pixel coordinates (at their center).
    tile_to_pixel = lambda t: int((t + 0.5) * step)
    pixelcoords  = [(tile_to_pixel(j), tile_to_pixel(i)) for (j,i) in tiles]
    latloncoords = [pixelcoord_to_latlon(y, x, zoom) for y,x in pixelcoords]

    # Pixel offset in upper-left  tile.
    off1 = (y1 % step, x1 % step)
    # Pixel offset in lower-right tile.
    off2 = (step - ((y2 + 1) % step) - 1, step - ((x2 + 1) % step) - 1)

    # Construct and fetch urls.
    urls = [build_filename_and_url(lat, lon, zoom, max_resolution, scale, api_key) for (lat, lon) in latloncoords]
    for (fname, url) in urls:
        if not os.path.isfile(cache_folder + fname):
            assert fetch_url(cache_folder + fname, url)
    
    # Load images into program workmemory.
    images = [read_image(cache_folder + fname) for (fname, _) in urls]
    images = [cut_logo(image, scale, margin) for image in images]

    imagecount = int(math.sqrt(len(tiles)))
    size = scale * (max_resolution - 2*margin)
    superimage = np.ndarray((height*size, width*size, 3), dtype="uint8")

    m = size
    for i in range(height):
        for j in range(width):
            superimage[i*m:(i+1)*m,j*m:(j+1)*m,:] = images[i*width+j]
    
    if not full_tiles:
        # Cut out part of interest (of latlon).
        off1 = (off1[0] * scale, off1[1] * scale) # Apply scale to (y,x) offset.
        off2 = (off2[0] * scale, off2[1] * scale) # Apply scale to (y,x) offset.
        superimage = superimage[off1[0]:-off2[0],off1[1]:-off2[1],:]
        # Note how we cut off in y with first axis (namely rows) and x in second axis (columns).
    
    # Store along coordinates of extracted image per pixel.
    pixelcoordinates = []
    for y in range(y1,y2):
        tmp = []
        for x in range(x1,x2):
            tmp.append(pixelcoord_to_latlon(y, x, zoom))
        pixelcoordinates.append(tmp)

    return superimage, pixelcoordinates


# Read API key stored locally.
def read_api_key():
    with open(cache_folder + "api_key.txt") as f: 
        api_key = f.read()
    return api_key
