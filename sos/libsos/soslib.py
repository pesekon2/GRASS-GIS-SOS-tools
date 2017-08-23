#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
############################################################################
#
# MODULE:	    sos tools
# AUTHOR(S):	Ondrej Pesek <pesej.ondrek@gmail.com>
# PURPOSE:	    Important functions used in *.sos modules
# COPYRIGHT:	(C) 2017 Ondrej Pesek and the GRASS Development Team
#
#		This program is free software under the GNU General
#		Public License (>=v2). Read the file COPYING that
#		comes with GRASS for details.
#
#############################################################################


import sys
import json
import xml.etree.ElementTree as etree
from osgeo import ogr, osr


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
                    data.update(
                        {timeStamp: values.split(tokenSeparator)[wantedIndex]})
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


def json2geojson(json_file):

    json_file = json.loads(
        json_file.decode('utf-8'))['ObservationCollection']['member']

    a = {"type": "FeatureCollection", "features": []}

    if 'srsName=' in json_file[0]['featureOfInterest']['geom']:
        epsg_part = json_file[0][
            'featureOfInterest']['geom'].split('srsName=')[1]
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
            data.update(
                {feature['result']['DataArray']['field'][i]['name']: values})

        data.update({'name': feature['name']})

        a['features'].append({"type": "Feature",
                              "geometry": {
                                  "type": point.GetGeometryName(),
                                  "coordinates": [point.GetX(), point.GetY()]},
                              "properties": {
                                  key: value for key, value in data.items()}
                              })

    return json.dumps(a, indent=4, sort_keys=True)


def get_description(service):
    """
    Return informations about the requested service if given necessary flags
    :param service: Service which we are requesting informations about
    """

    if flags['o'] is True:
        if flags['g'] is False:
            print('SOS offerings:')
        for offering in service.offerings:
            print(offering.id)

    for offering in options['offering'].split(','):
        if flags['v'] is True:
            if flags['g'] is False:
                print('Observed properties of '
                      '{} offering:'.format(offering))
            for observed_property in service[offering].observed_properties:
                print(observed_property)

        if flags['p'] is True:
            if flags['g'] is False:
                print('Procedures of {} offering:'.format(offering))
            for procedure in service[offering].procedures:
                print(procedure.split(':')[-1])

        if flags['t'] is True:
            beginTimestamp = str(service[offering].begin_position)
            beginTimestamp = 'T'.join(beginTimestamp.split(' '))
            endTimestamp = str(service[offering].end_position)
            endTimestamp = 'T'.join(endTimestamp.split(' '))
            if flags['g'] is False:
                print('Begin timestamp/end timestamp of '
                      '{} offering:'.format(options['offering']))
                print('{}/{}'.format(beginTimestamp, endTimestamp))
            else:
                print('start_time={}'.format(beginTimestamp))
                print('end_time={}'.format(endTimestamp))

    sys.exit(0)


def handle_not_given_options(service, offering=None, procedure=None,
                             observedProperties=None, eventTime=None):
    """
    If there are not given some options, use the full scale
    :param service: Service which we are requesting parameters for
    :param offering: A collection of sensors used to conveniently group them up
    :param procedure: Who provide the observations (mostly the sensor)
    :param observed_properties: The phenomena that are observed
    :param eventTime: Timestamp of first,last requested observation
    """
    if procedure == '':
        procedure = None
    else:
        procedure = procedure

    if observedProperties == '':
        observed_properties = ''
        for observed_property in service[offering].observed_properties:
            observed_properties += '{},'.format(observed_property)
        observed_properties = observed_properties[:-1]
    else:
        observed_properties = observedProperties

    if eventTime == '':
        beginTimestamp = str(service[offering].begin_position)
        beginTimestamp = 'T'.join(beginTimestamp.split(' '))
        endTimestamp = str(service[offering].end_position)
        endTimestamp = 'T'.join(endTimestamp.split(' '))
        eventTime = '{}/{}'.format(beginTimestamp, endTimestamp)
    else:
        eventTime = eventTime

    return procedure, observed_properties, eventTime
