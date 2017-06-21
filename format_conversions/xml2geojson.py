import xml.etree.ElementTree as etree
import json


def xml2geojson(xml_file):
    tree = etree.ElementTree(etree.fromstring(xml_file))
    a = {"type": "FeatureCollection", "features": []}

    root = tree.getroot()

    for child in root.iter():
        if 'location' in child.tag:
            a.update({"crs": {
                "type": "name",
                "properties": {"name": list(child)[0].attrib['srsName']}}})
            break

    for child in root.findall('{http://www.opengis.net/om/1.0}member'):
        data = dict()
        valuesNames = list()
        nameFound = False
        separator = ','

        for item in child.iter():

            if 'name' in item.tag and nameFound is False:
                data.update({'name': item.text})
                nameFound = True
            elif 'field' in item.tag:
                valuesNames.append(item.attrib['name'])
                data.update({item.attrib['name']: ''})
            elif 'TextBlock' in item.tag:
                tokenSeparator = item.attrib['tokenSeparator']
                blockSeparator = item.attrib['blockSeparator']
            elif 'values' in item.tag:
                for values in item.text.split(blockSeparator):
                    valuesIndex = 0
                    for value in values.split(tokenSeparator):
                        data[valuesNames[valuesIndex]] += '%s,' % value
                        valuesIndex += 1
                for name in valuesNames:
                    data[name] = data[name][:-1]
            elif 'location' in item.tag:
                point = list(item)[0]
                geometryType = point.tag.split('}')[1]
                geometryCoords = list(point)[0].text.split(separator)
                for i in range(len(geometryCoords)):
                    geometryCoords[i] = float(geometryCoords[i])

        a['features'].append({"type": "Feature",
                              "geometry": {
                                  "type": geometryType,
                                  "coordinates": geometryCoords},
                              "properties": {
                                  key: value for key, value in data.items()}
                              })

    return json.dumps(a, indent=4, sort_keys=True)
