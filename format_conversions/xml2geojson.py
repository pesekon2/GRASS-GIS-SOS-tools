import xml.etree.ElementTree as etree
import json


def xml2geojson(xml_file, observedProperty):
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
        currentIndex = 1

        for item in child.iter():

            if 'name' in item.tag and nameFound is False:
                data.update({'name': item.text})
                nameFound = True
            elif 'field' in item.tag:
                valuesNames.append(item.attrib['name'])
            elif 'Quantity' in item.tag:
                if observedProperty in item.attrib['definition']:
                    wantedIndex = currentIndex
                else:
                    currentIndex += 1
            elif 'TextBlock' in item.tag:
                tokenSeparator = item.attrib['tokenSeparator']
                blockSeparator = item.attrib['blockSeparator']
            elif 'values' in item.tag:
                for values in item.text.split(blockSeparator):
                    timeStamp = 't%s' % values.split(tokenSeparator)[0]
                    for character in [':', '-', '+']:
                        timeStamp = ''.join(timeStamp.split(character))
                    data.update({timeStamp: values.split(tokenSeparator)[wantedIndex]})
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
