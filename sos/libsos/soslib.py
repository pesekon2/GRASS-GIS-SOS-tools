#!/usr/bin/env python3
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
import os
import json
import xml.etree.ElementTree as etree
from osgeo import ogr, osr
from grass.script import core as grass
from grass.script import run_command


def xml2geojson(xml_file, observedProperty, importEmpty=False):
    """
    Convert file in standard xml (text/xml;subtype="om/1.0.0") to geoJSON
    :param xml_file: Response from SOS server in text/xml;subtype="om/1.0.0"
    :param observedProperty: One observed property from SOS response
    :param importEmpty: Import also empty procedures
    :return json.dumps: Parsed response in geoJSON
    """

    tree = etree.ElementTree(etree.fromstring(xml_file))
    a = {"type": "FeatureCollection", "features": []}

    root = tree.getroot()
    crs = 0

    for child in root.iter():
        if 'location' in child.tag:
            if crs and crs != list(child)[0].attrib['srsName']:
                raise ValueError('CRS of different points within one offering '
                                 'do not match.')
            crs = list(child)[0].attrib['srsName']

            a.update({"crs": {
                "type": "name",
                "properties": {"name": crs}}})

    for child in root.findall('{http://www.opengis.net/om/1.0}member'):
        data = dict()
        valuesNames = list()
        nameFound = False
        separator = ','
        currentIndex = 1
        include = True

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
                if not item.text:
                    if importEmpty:
                        values = 0
                    else:
                        include = False
                    run_command(
                        'g.message',
                        flags='w',
                        message='No observations of '
                                '{} found for procedure {}.'.format(
                            observedProperty,
                            data['name'])
                    )
                    break
                for values in item.text.split(blockSeparator):
                    timeStamp = 't%s' % values.split(tokenSeparator)[0]
                    for character in [':', '-', '+']:
                        timeStamp = ''.join(timeStamp.split(character))

                    data.update({timeStamp: values.split(
                        tokenSeparator)[wantedIndex]})
            elif 'location' in item.tag:
                point = list(item)[0]
                geometryType = point.tag.split('}')[1]
                geometryCoords = list(point)[0].text.split(separator)
                for i in range(len(geometryCoords)):
                    geometryCoords[i] = float(geometryCoords[i])

        if include:
            a['features'].append(
                {"type": "Feature",
                 "geometry": { "type": geometryType,
                               "coordinates": geometryCoords},
                 "properties": {
                     key: value for key, value in data.items()}
                 })

    return json.dumps(a, indent=4, sort_keys=True)


def json2geojson(json_file):
    # TODO: Has to be updated, doesn't work really well (use xml2geojson)
    """
    Convert file in json format to geoJSON
    :param json_file: Response from SOS server in json format
    :return json.dumps: Parsed response in geoJSON
    """

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


def get_description(service, options, flags):
    """
    Return informations about the requested service if given necessary flags
    :param service: Service which we are requesting informations about
    :param options: Parameters from the module
    :param flags: Flags from the module
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
                      '{} offering:'.format(offering))
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
    :param observedProperties: The phenomena that are observed
    :param eventTime: Timestamp of first,last requested observation
    """
    if procedure == '':
        procedure = None
    else:
        procedure = procedure

    if observedProperties == '':
        observed_properties = service[offering].observed_properties
    else:
        observed_properties = observedProperties.split(',')

    if eventTime == '':
        beginTimestamp = str(service[offering].begin_position)
        beginTimestamp = 'T'.join(beginTimestamp.split(' '))
        endTimestamp = str(service[offering].end_position)
        endTimestamp = 'T'.join(endTimestamp.split(' '))
        eventTime = '{}/{}'.format(beginTimestamp, endTimestamp)
    else:
        eventTime = eventTime

    return procedure, observed_properties, eventTime


def check_missing_params(offering, output):
    """
    Check whether all the necessary params or flags were defined
    :param offering: A collection of sensors used to conveniently group them up
    :param output: prefix for output maps
    """

    if offering == '' or output == '':
        if sys.version_info[0] >= 3:
            sys.tracebacklimit = None
        else:
            sys.tracebacklimit = 0
        raise AttributeError(
            "You have to define any flags or use 'output' and 'offering' "
            "parameters to get the data")

def get_target_crs():
    """
    Return target projection of current LOCATION
    :return target: SpatialReference() object of location projection
    """

    target_crs = grass.read_command('g.proj', flags='fj').rstrip(os.linesep)
    target = osr.SpatialReference()
    target.ImportFromProj4(target_crs)
    if target == 'XY location (unprojected)':
        grass.fatal("Sorry, XY locations are not supported!")

    return target

def standardize_table_name(nameParts):
    """
    Drops unsupported characters from the tablename
    :param nameParts: List of strings to be included in the tablename
    :return tableName: Tablename with unsupported characters replaced with '_'
    """

    tableName = nameParts[0]
    for i in nameParts[1:]:
        tableName = '{}_{}'.format(tableName, i)

    if ':' in tableName:
        tableName = '_'.join(tableName.split(':'))
    if '-' in tableName:
        tableName = '_'.join(tableName.split('-'))
    if '.' in tableName:
        tableName = '_'.join(tableName.split('.'))

    return tableName

def get_transformation(crs, target):
    """
    Get the transformation key to be used to transform your sensor coordinates
    :param crs: The original CRS of sensors
    :param target: The target CRS for sensors
    :return transform: The transformation key
    """

    source = osr.SpatialReference()
    source.ImportFromEPSG(crs)
    transform = osr.CoordinateTransformation(source, target)

    return transform