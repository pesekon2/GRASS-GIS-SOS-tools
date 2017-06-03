import json
from osgeo import ogr, osr

def json2geojson(json_file):

    json_file = json.loads(json_file.decode('utf-8'))['ObservationCollection']['member']

    a = {"type": "FeatureCollection", "features": []}

    if 'srsName=' in json_file[0]['featureOfInterest']['geom']:
        epsg_part = json_file[0]['featureOfInterest']['geom'].split('srsName=')[1]
        crs = ''
        i = 0
        while epsg_part[i] != '>':
            crs += epsg_part[i]
            i += 1
        crs = crs[1:-1]
        a.update({"crs": {"type": "name", "properties": {"name": crs}}})


    for feature in json_file:
        geom = feature['featureOfInterest']['geom']
        point = ogr.CreateGeometryFromGML(geom)

        data = {}
        for i in range(int(feature['result']['DataArray']['elementCount'])):
            values = []
            for j in feature['result']['DataArray']['values']:
                values.append(j[i])
            data.update({feature['result']['DataArray']['field'][i]['name']:values})

        data.update({'name': feature['name']})

        a['features'].append({"type": "Feature",
                              "geometry": {
                                  "type": point.GetGeometryName(),
                                  "coordinates": [point.GetX(),point.GetY()]},
                              "properties": {
                                  key: value for key, value in data.items()}
                              })

    return json.dumps(a, indent=4, sort_keys=True)