# encoding: utf8

"""
This script watches the Cologne area for
AED entries and looks for matches in our
aed.csv source

Dieses Script lädt Defibrillatoren-Daten
innerhalb der Kölner Stadtgrenzen und prüft,
ob diese in unserer Quelle aed.csv enthalten
sind.
"""

import sys
import json
import csv
import requests
from shapely.geometry import Polygon, Point
from pyproj import Proj
from pyproj import transform


def get_bounds():
    """
    Importiere Grenze von Köln
    als Shapely-Polygon
    """
    f = open("../../geo-base/city-boundary/cityboundary.geojson")
    data = json.loads(f.read())
    f.close()
    coords = data["coordinates"][0]
    return Polygon(coords)

def load_osm_aeds():
    xml = """<osm-script output="json" timeout="25">
      <query type="node">
        <has-kv k="emergency" v="defibrillator"/>
        <bbox-query n="51.2" e="7.2" s="50.8" w="6.7" />
      </query>
      <print mode="meta"/>
    </osm-script>"""
    bounds = get_bounds()
    out = {}
    r = requests.post("http://overpass-api.de/api/interpreter", data=xml)
    for item in r.json()["elements"]:
        position = Point([item["lon"], item["lat"]])
        if bounds.contains(position):
            out[str(item["id"])] = item
    return out


def load_csv_aeds():
    out = []
    headers = []
    with open("aed.csv", "rb") as csvfile:
        reader = csv.reader(csvfile)
        rowcount = -1
        for row in reader:
            rowcount += 1
            if rowcount == 0:
                headers = row
            else:
                record = {}
                for n in range(len(row)):
                    if row[n] == "":
                        row[n] = None
                    if row[n] is not None:
                        if headers[n] in ["latitude", "longitude"]:
                            row[n] = float(row[n])
                    record[headers[n]] = row[n]
                out.append(record)
    return out

wgs84_projection = Proj(init="epsg:4326")
metric_projection = Proj(init="epsg:25832")

def distance(x1, y1, x2, y2):
    x1, y1 = transform(wgs84_projection,
        metric_projection, float(x1), float(y1), radians=False)
    x2, y2 = transform(wgs84_projection,
        metric_projection, float(x2), float(y2), radians=False)
    #print x1, y1, x2, y2
    return Point(x1, y1).distance(Point(x2, y2))


if __name__ == "__main__":
    aeds = load_csv_aeds()
    osm_aeds = load_osm_aeds()
    for osm_id in osm_aeds.keys():
        found = False
        changes = []
        our_mapped_id = None
        for aed in aeds:
            if str(osm_id) == str(aed["osm_node_id"]):
                found = True
                our_mapped_id = aed["osm_node_id"]
                #print("OSM node %s maps to our ID %s" % (osm_id, aed["id"]))
                # check difference
                if (str(osm_aeds[osm_id]["lon"]) != str(aed["longitude"]) or 
                    str(osm_aeds[osm_id]["lat"]) != str(aed["latitude"])):
                    # distance form our to OSM position
                    dist = distance(osm_aeds[osm_id]["lon"],
                            osm_aeds[osm_id]["lat"],
                            aed["longitude"], aed["latitude"])
                    if dist > 0.1:
                        sys.stderr.write("OSM ID %s, our ID %s: position is: x=%s, y=%s, distance: %.2f m\n" % (
                            osm_id, aed["id"], osm_aeds[osm_id]["lon"],
                            osm_aeds[osm_id]["lat"], dist))
                        changes.append("position")
                continue
        #if changes != []:

        if not found:
            sys.stderr.write("OSM ID %s is not in aed.csv:\n" % osm_id)
            sys.stderr.write(json.dumps(osm_aeds[osm_id], indent=4))
