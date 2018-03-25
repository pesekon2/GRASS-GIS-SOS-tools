#!/usr/bin/env python
#
############################################################################
#
# MODULE:	    v.in.sos
# AUTHOR(S):	Ondrej Pesek <pesej.ondrek@gmail.com>
# PURPOSE:	    Import data from SOS server as a vector layer to GRASS GIS
# COPYRIGHT:	(C) 2017 Ondrej Pesek and the GRASS Development Team
#
#		This program is free software under the GNU General
#		Public License (>=v2). Read the file COPYING that
#		comes with GRASS for details.
#
#############################################################################

#%module
#% description: Import data from SOS server as a vector layer to GRASS GIS.
#% keyword: vector
#% keyword: import
#% keyword: SOS
#%end
#%flag
#% key: l
#% description: Create a new layer for each observed property and import procedures as rows
#%end
#%flag
#% key: s
#% description: Skip import of observation, import only procedure info for all procedures of offering
#%end
#%flag
#% key: i
#% description: Import also procedures with no observations
#%end
#%flag
#% key: v
#% description: Print observed properties for given url and offering
#% guisection: Print
#%end
#%flag
#% key: o
#% description: Print offerings for given url
#% guisection: Print
#%end
#%flag
#% key: p
#% description: Print procedures for given url and offering
#% guisection: Print
#%end
#%flag
#% key: t
#% description: Print begin and end timestamps for given url and offering
#% guisection: Print
#%end
#%flag
#% key: g
#% description: Print informations in shell script style
#% guisection: Print
#%end
#%option
#% key: url
#% type: string
#% description: Base URL starting with 'http' and ending in '?'
#% required: yes
#%end
#%option G_OPT_V_OUTPUT
#% required: no
#% guisection: Request
#%end
#%option
#% key: offering
#% type: string
#% description: A collection of sensor used to conveniently group them up
#% required: no
#% multiple: yes
#% guisection: Request
#%end
#%option
#% key: timeout
#% type: integer
#% description: Timeout for SOS request
#% required: no
#% answer: 30
#% guisection: Request
#%end
#%option
#% key: response_format
#% type: string
#% options: text/xml;subtype="om/1.0.0", application/json
#% description: Format of data output
#% answer: text/xml;subtype="om/1.0.0"
#% required: no
#% guisection: Request
#%end
#%option
#% key: observed_properties
#% type: string
#% description: The phenomena that are observed
#% required: no
#% guisection: Request
#% multiple: yes
#%end
#%option
#% key: procedure
#% type: string
#% description: Who provide the observations (mostly the sensor)
#% required: no
#% guisection: Request
#%end
#%option
#% key: event_time
#% type: string
#% label: Timestamp of first/timestamp of last requested observation
#% description: Example: 2015-06-01T00:00:00+0200/2015-06-03T00:00:00+0200
#% required: no
#% guisection: Request
#%end
#%option
#% key: granularity
#% type: string
#% label: Granularity used to aggregate data
#% description: Based on the hierarchy that 1 year equals 365.2425 days
#% required: no
#% guisection: Data
#%end
#%option
#% key: method
#% type: string
#% label: Aggregation method used in case of granularity
#% options: average, sum
#% answer: average
#% required: no
#% guisection: Data
#%end
#%option
#% key: version
#% type: string
#% description: Version of SOS server
#% guisection: Request
#% options: 1.0.0, 2.0.0
#% answer: 1.0.0
#%end
#%option
#% key: username
#% type: string
#% description: Username with access to server
#% guisection: User
#%end
#%option
#% key: password
#% type: string
#% description: Password according to username
#% guisection: User
#%end
#%rules
#% requires_all: -v, offering, url
#% requires_all: -p, offering, url
#% requires_all: -t, offering, url
#% requires: -o, url
#%end


import sys
import os
import json
import time
import datetime
try:
    from owslib.sos import SensorObservationService
    from owslib.swe.sensor.sml import SensorML
    from grass.script import parser, run_command, read_command
    from grass.script import core as grass
    from grass.pygrass.vector import VectorTopo
    from grass.pygrass.vector.geometry import Point
    from grass.pygrass.vector.table import Link
    from grass.pygrass.utils import get_lib_path
except ImportError as e:
    sys.stderr.write('Error importing internal libs. '
                     'Did you run the script from GRASS GIS?\n')
    raise(e)

path = get_lib_path(modname='sos', libname='libsos')
if path is None:
    grass.script.fatal('Not able to find the sos library directory.')
sys.path.append(path)
from soslib import *


def cleanup():
    pass


def main():
    parsed_obs = dict()
    layerscount = 0

    service = SensorObservationService(options['url'],
                                       version=options['version'],
                                       username=options['username'],
                                       password=options['password'])

    if any(value is True and key in [
      'o', 'v', 'p', 't'] for key, value in flags.iteritems()):
        get_description(service, options, flags)

    check_missing_params(options['offering'], options['output'])

    if options['granularity'] != '':
        import grass.temporal as tgis
        tgis.init()
        secondsGranularity = int(tgis.gran_to_gran(options['granularity'],
                                                   '1 second',
                                                   True))
    else:
        secondsGranularity = 1

    target = get_target_crs()

    run_command('g.remove', 'f', type='vector', name=options['output'])
    new = VectorTopo(options['output'])

    for off in options['offering'].split(','):
        # TODO: Find better way than iteration (at best OWSLib upgrade)
        procedure, observed_properties, event_time = handle_not_given_options(
            service, off, options['procedure'], options['observed_properties'],
            options['event_time'])

        if flags['s']:
            create_maps(_, off, _, new, _, _, service, target, _, procedure)
        else:
            try:
                obs = service.get_observation(
                    offerings=[off],
                    responseFormat=options['response_format'],
                    observedProperties=observed_properties,
                    procedure=procedure,
                    eventTime=event_time,
                    timeout=int(options['timeout']),
                    username=options['username'],
                    password=options['password'])
            except:
                # TODO: catch errors properly (e.g. timeout)
                grass.fatal('Request did not succeed!')

            try:
                if options['version'] in ['1.0.0', '1.0'] and str(
                  options['response_format']) == 'text/xml;subtype="om/1.0.0"':
                    for prop in observed_properties:
                        parsed_obs.update({prop: xml2geojson(obs,
                                                             prop,
                                                             flags['i'])})
                elif str(options['response_format']) == 'application/json':
                    for prop in observed_properties:
                        parsed_obs.update({prop: json2geojson(obs, prop)})
            except AttributeError:
                if sys.version >= (3, 0):
                    sys.tracebacklimit = None
                else:
                    sys.tracebacklimit = 0
                raise AttributeError(
                    'There is no data for at least one of your procedures, '
                    'could  you change the time parameter, observed '
                    'properties, procedures or offerings')
            except ValueError as e:
                if sys.version >= (3, 0):
                    sys.tracebacklimit = None
                else:
                    sys.tracebacklimit = 0
                raise e

            create_maps(parsed_obs, off, layerscount, new,
                        secondsGranularity, event_time, service, target,
                        observed_properties)
            layerscount += len(parsed_obs)
        return 0


def create_maps(parsed_obs, offering, layer, new, secondsGranularity,
                event_time, service, target, obsProps, procedures=None):
    """
    Add layers representing offerings and observed properties to the vector map
    :param parsed_obs: Observations for a given offering in geoJSON format
    :param offering: A collection of sensors used to conveniently group them up
    :param layer: Count of yet existing layers in vector map
    :param new: Given vector map which should be updated with new layers
    :param secondsGranularity: Granularity in seconds
    :param event_time: Timestamp of first/of last requested observation
    :param service: SensorObservationService() type object of request
    :param procedures: List of queried procedures (observation providers)
    """

    if flags['s']:
        maps_without_observations(offering, new, service, procedures, target)
    else:
        full_maps(parsed_obs, offering, layer, new, secondsGranularity,
                  event_time, target, obsProps)


def maps_without_observations(offering, new, service, procedures, target):
    """
    Import just vector points/sensors without their observations
    :param offering: A collection of sensors used to conveniently group them up
    :param new: Given vector map which should be updated with new layers
    :param service: SensorObservationService() type object of request
    :param procedures: List of queried procedures (observation providors)
    """
    points = dict()
    freeCat = 1

    cols = [(u'cat', 'INTEGER PRIMARY KEY'),
            (u'name', 'varchar'),
            (u'description', 'varchar'),
            (u'keywords', 'varchar'),
            (u'sensor_type', 'varchar'),
            (u'system_type', 'varchar'),
            (u'crs', 'INTEGER'),
            (u'x', 'DOUBLE'),
            (u'y', 'DOUBLE'),
            (u'z', 'DOUBLE')]
    # new = Vector(new)
    if new.is_open() is False:
        new.open('w', tab_name=options['output'], tab_cols=cols)
    offs = [o.id for o in service.offerings]
    off_idx = offs.index(offering)
    outputFormat = service.get_operation_by_name('DescribeSensor').parameters[
        'outputFormat']['values'][0]

    if procedures:
        procedures = procedures.split(',')
    else:
        procedures = service.offerings[off_idx].procedures

    for proc in procedures:
        response = service.describe_sensor(procedure=proc,
                                           outputFormat=outputFormat)
        root = SensorML(response)
        system = root.members[0]
        name = system.name
        desc = system.description
        keywords = ','.join(system.keywords)
        sensType = system.classifiers['Sensor Type'].value
        sysType = system.classifiers['System Type'].value
        crs = int(system.location[0].attrib['srsName'].split(':')[-1])
        coords = system.location[0][0].text.replace('\n', '')
        sx = float(coords.split(',')[0])
        sy = float(coords.split(',')[1])
        sz = float(coords.split(',')[2])
        # Set source projection from SOS
        transform = get_transformation(crs, target)
        point = ogr.CreateGeometryFromWkt('POINT ({} {} {})'.format(sx,
                                                                    sy,
                                                                    sz))
        point.Transform(transform)
        x = point.GetX()
        y = point.GetY()
        z = point.GetZ()
        if name not in points.keys():
            points.update({name: freeCat})
            point = Point(x, y, z)
            new.write(point, cat=freeCat, attrs=(
                      u'{}'.format(system.name.decode('utf-8')),
                      system.description,
                      ','.join(system.keywords),
                      system.classifiers['Sensor Type'].value,
                      system.classifiers['System Type'].value,
                      crs,
                      float(coords.split(',')[0]),
                      float(coords.split(',')[1]),
                      float(coords.split(',')[2]),))
            freeCat += 1
    new.table.conn.commit()
    new.close(build=True)


def full_maps(parsed_obs, offering, layer, new, secondsGranularity,
              event_time, target, obsProps):
    """
    Import vector points/sensors with their observations in the attribute table
    :param parsed_obs: Observations for a given offering in geoJSON format
    :param offering: A collection of sensors used to conveniently group them up
    :param layer: Count of yet existing layers in vector map
    :param new: Given vector map which should be updated with new layers
    :param secondsGranularity: Granularity in seconds
    :param event_time: Timestamp of first/of last requested observation
    """
    i = layer + 1
    points = dict()
    freeCat = 1

    timestampPattern = '%Y-%m-%dT%H:%M:%S'  # TODO: Timezone
    startTime = event_time.split('+')[0]
    epochS = int(time.mktime(time.strptime(startTime, timestampPattern)))
    endTime = event_time.split('+')[1].split('/')[1]
    epochE = int(time.mktime(time.strptime(endTime, timestampPattern)))

    if flags['l']:
        for key, observation in parsed_obs.iteritems():

            tableName = standardize_table_name([options['output'], offering,
                                                key])

            data = json.loads(observation)
            # get the transformation between source and target crs
            crs = data['crs']
            crs = int(crs['properties']['name'].split(':')[-1])
            transform = get_transformation(crs, target)


            intervals = {}
            for secondsStamp in range(epochS, epochE + 1, secondsGranularity):
                intervals.update({secondsStamp: dict()})

            emptyProcs = list()
            timestampPattern = 't%Y%m%dT%H%M%S'  # TODO: Timezone

            cols = [(u'cat', 'INTEGER PRIMARY KEY'), (u'name', 'VARCHAR')]
            for a in data['features']:
                name = a['properties']['name']
                empty = True

                if name not in points.keys():
                    if new.is_open() is False:
                        new.open('w')

                    points.update({name: freeCat})

                    # transform the geometry into the target crs
                    sx, sy, sz = a['geometry']['coordinates']
                    point = ogr.CreateGeometryFromWkt('POINT ({} {} {})'.format(
                        sx, sy, sz))
                    point.Transform(transform)
                    coords = (point.GetX(), point.GetY(), point.GetZ())

                    new.write(Point(*coords), cat=freeCat)
                    freeCat += 1

                for timestamp, value in a['properties'].iteritems():
                    if timestamp != 'name':
                        if empty:
                            empty = False
                        observationStartTime = timestamp[:-4]
                        secondsTimestamp = int(time.mktime(
                            time.strptime(observationStartTime, timestampPattern)))
                        for interval in intervals.keys():
                            if secondsTimestamp >= interval \
                                    and secondsTimestamp < (
                                                interval + secondsGranularity):
                                if name in intervals[interval].keys():
                                    intervals[interval][name].append(float(value))
                                else:
                                    timestamp2 = datetime.datetime.fromtimestamp(
                                        interval).strftime('t%Y%m%dT%H%M%S')
                                    intervals[interval].update(
                                        {name: [float(value)]})
                                    if (u'%s' % timestamp2, 'DOUBLE') not in cols:
                                        cols.append((u'%s' % timestamp2, 'DOUBLE'))
                                break

                if empty:
                    emptyProcs.append(value)  # in value there is name of last proc

            if len(cols) > 2000:
                grass.warning(
                    'Recommended number of columns is less than 2000, you have '
                    'reached {}\nYou should set an event_time with a smaller range'
                    ' or recompile SQLite limits as described at '
                    'https://sqlite.org/limits.html'.format(len(cols)))

            link = Link(
                layer=i, name=tableName, table=tableName, key='cat',
                database='$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db',
                driver='sqlite')

            if new.is_open():
                new.close()

            new.open('rw')
            new.dblinks.add(link)
            new.table = new.dblinks[i - 1].table()
            new.table.create(cols)
            inserts = dict()

            # create attr tab inserts for empty procs
            for emptyProc in emptyProcs:
                insert = [None] * len(cols)
                insert[0] = points[emptyProc]
                insert[1] = emptyProc
                inserts.update({emptyProc: insert})

            # create attr tab inserts for procs with observations
            for interval in intervals.keys():
                if len(intervals[interval]) != 0:
                    timestamp = datetime.datetime.fromtimestamp(
                        interval).strftime('t%Y%m%dT%H%M%S')

                    for name, values in intervals[interval].iteritems():
                        if options['method'] == 'average':
                            aggregatedValue = sum(values) / len(values)
                        elif options['method'] == 'sum':
                            aggregatedValue = sum(values)

                        if name not in inserts.keys():
                            insert = [None] * len(cols)
                            insert[0] = points[name]
                            insert[1] = name
                            insert[cols.index((timestamp,
                                               'DOUBLE'))] = aggregatedValue
                            inserts.update({name: insert})
                        else:
                            inserts[name][cols.index((timestamp,
                                                      'DOUBLE'))] = aggregatedValue

            for insert in inserts.values():
                new.table.insert(tuple(insert))
                new.table.conn.commit()

            new.close(build=False)
            run_command('v.build', quiet=True, map=options['output'])

            i += 1
    else:
        for propIndex in range(len(obsProps)):
            obsProps[propIndex] = standardize_table_name([obsProps[propIndex]])

        for key, observation in parsed_obs.iteritems():
            print('Working on the observed property {}'.format(key))
            key = standardize_table_name([key])

            data = json.loads(observation)
            # get the transformation between source and target crs
            crs = data['crs']
            crs = int(crs['properties']['name'].split(':')[-1])
            transform = get_transformation(crs, target)

            emptyProcs = list()
            timestampPattern = 't%Y%m%dT%H%M%S'  # TODO: Timezone

            cols = [(u'connection', 'INTEGER'), (u'timestamp', 'VARCHAR')]
            for obsProp in obsProps:
                cols.append((u'{}'.format(obsProp), 'DOUBLE'))

            for a in data['features']:
                name = a['properties']['name']

                tableName = standardize_table_name([options['output'], offering, name])

                intervals = {}
                for secondsStamp in range(epochS, epochE + 1,
                                          secondsGranularity):
                    intervals.update({secondsStamp: dict()})

                empty = True

                if name not in points.keys():
                    if new.is_open() is False:
                        new.open('w')

                    points.update({name: freeCat})

                    # transform the geometry into the target crs
                    sx, sy, sz = a['geometry']['coordinates']
                    point = ogr.CreateGeometryFromWkt('POINT ({} {} {})'.format(
                        sx, sy, sz))
                    point.Transform(transform)
                    coords = (point.GetX(), point.GetY(), point.GetZ())

                    new.write(Point(*coords), cat=freeCat)
                    freeCat += 1

                for timestamp, value in a['properties'].iteritems():
                    if timestamp != 'name':
                        if empty:
                            empty = False
                        observationStartTime = timestamp[:-4]
                        secondsTimestamp = int(time.mktime(
                            time.strptime(observationStartTime, timestampPattern)))
                        for interval in intervals.keys():
                            if secondsTimestamp >= interval \
                                    and secondsTimestamp < (
                                                interval + secondsGranularity):
                                if name in intervals[interval].keys():
                                    intervals[interval][name].append(float(value))
                                else:
                                    intervals[interval].update(
                                        {name: [float(value)]})
                                break

                if empty:
                    emptyProcs.append(value)  # in value there is name of last proc

                if new.is_open():
                    # new.close()
                    new.close(build=False)
                    run_command('v.build', quiet=True, map=options['output'])
                new.open('rw')

                yetExisting = False
                if not new.dblinks.by_name(tableName):
                    link = Link(
                        layer=i, name=tableName, table=tableName, key='connection',
                        database='$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db',
                        driver='sqlite')
                    new.dblinks.add(link)
                    new.table = new.dblinks[i - 1].table()
                    new.table.create(cols)
                else:
                    yetExisting = True

                inserts = dict()

                # create attr tab inserts for empty procs
                for emptyProc in emptyProcs:
                    insert = [None] * len(cols)
                    insert[0] = points[emptyProc]
                    insert[1] = emptyProc
                    inserts.update({emptyProc: insert})

                # create attr tab inserts for procs with observations
                for interval in intervals.keys():
                    if len(intervals[interval]) != 0:
                        timestamp = datetime.datetime.fromtimestamp(
                            interval).strftime('t%Y%m%dT%H%M%S')
                        for name, values in intervals[interval].iteritems():
                            if options['method'] == 'average':
                                aggregatedValue = sum(values) / len(values)
                            elif options['method'] == 'sum':
                                aggregatedValue = sum(values)

                            if yetExisting:
                                a = read_command(
                                    'db.select',
                                    sql='SELECT COUNT(*) FROM {} WHERE timestamp="{}"'.format(
                                        tableName, timestamp
                                    ))
                                if a.split('\n')[1] != '0':
                                    run_command(
                                        'db.execute',
                                        sql='UPDATE {} SET {}={} WHERE timestamp="{}";'.format(
                                            tableName, key, aggregatedValue,
                                            timestamp))
                                    continue

                            # if name not in inserts.keys():
                            insert = [None] * len(cols)
                            insert[0] = points[name]
                            insert[1] = timestamp
                            insert[cols.index(
                                (key, 'DOUBLE'))] = aggregatedValue

                            new.table.insert(tuple(insert))
                    new.table.conn.commit()

                i += 1

            new.close()


if __name__ == "__main__":
    options, flags = parser()
    main()
