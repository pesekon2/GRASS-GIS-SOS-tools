#!/usr/bin/env python3
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
    raise e

path = get_lib_path(modname='sos', libname='libsos')
if path is None:
    grass.script.fatal('Not able to find the sos library directory.')
sys.path.append(path)


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
      'o', 'v', 'p', 't'] for key, value in flags.items()):
        soslib.get_description(service, options, flags)

    soslib.check_missing_params(options['offering'], options['output'])

    if options['granularity'] != '':
        import grass.temporal as tgis
        tgis.init()
        seconds_granularity = int(tgis.gran_to_gran(options['granularity'],
                                                    '1 second',
                                                    True))
    else:
        seconds_granularity = 1

    target = soslib.get_target_crs()

    run_command('g.remove', 'f', type='vector', name=options['output'])
    new = VectorTopo(options['output'])

    for off in options['offering'].split(','):
        # TODO: Find better way than iteration (at best OWSLib upgrade)
        out = soslib.handle_not_given_options(
            service, off, options['procedure'], options['observed_properties'],
            options['event_time'])
        procedure, observed_properties, event_time = out

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
                        parsed_obs.update(
                            {prop: soslib.xml2geojson(obs, prop, flags['i'])})
                elif str(options['response_format']) == 'application/json':
                    for prop in observed_properties:
                        parsed_obs.update(
                            {prop: soslib.json2geojson(obs, prop)})
            except AttributeError:
                if sys.version_info[0] >= 3:
                    sys.tracebacklimit = None
                else:
                    sys.tracebacklimit = 0
                raise AttributeError(
                    'There is no data for at least one of your procedures, '
                    'could  you change the time parameter, observed '
                    'properties, procedures or offerings')
            except ValueError as e:
                if sys.version_info[0] >= 3:
                    sys.tracebacklimit = None
                else:
                    sys.tracebacklimit = 0
                raise e

            create_maps(parsed_obs, off, layerscount, new,
                        seconds_granularity, event_time, service, target,
                        observed_properties)
            layerscount += len(parsed_obs)
        return 0


def create_maps(parsed_obs, offering, layer, new, seconds_granularity,
                event_time, service, target, obs_props, procedures=None):
    """Add layers to the vector map.

    Layers represent offerings and observed properties

    :param parsed_obs: Observations for a given offering in geoJSON format
    :param offering: A collection of sensors used to conveniently group them up
    :param layer: Count of yet existing layers in vector map
    :param new: Given vector map which should be updated with new layers
    :param seconds_granularity: Granularity in seconds
    :param event_time: Timestamp of first/of last requested observation
    :param service: SensorObservationService() type object of request
    :param target: The target CRS for sensors
    :param obs_props: Oberved properties
    :param procedures: List of queried procedures (observation providers)
    """
    if flags['s']:
        maps_without_observations(offering, new, service, procedures, target)
    else:
        i = layer + 1
        timestamp_pattern = '%Y-%m-%dT%H:%M:%S'  # TODO: Timezone
        start_time = event_time.split('+')[0]
        epoch_s = int(time.mktime(time.strptime(start_time,
                                                timestamp_pattern)))
        end_time = event_time.split('+')[1].split('/')[1]
        epoch_e = int(time.mktime(time.strptime(end_time, timestamp_pattern)))

        if not flags['l']:
            maps_rows_timestamps(parsed_obs, offering, new,
                                 seconds_granularity, target, obs_props,
                                 epoch_s, epoch_e, i)
        else:
            maps_rows_sensors(parsed_obs, offering, new, seconds_granularity,
                              target, epoch_s, epoch_e, layer+1)


def maps_without_observations(offering, new, service, procedures, target):
    """Import just vector points/sensors without their observations.

    :param offering: A collection of sensors used to conveniently group them up
    :param new: Given vector map which should be updated with new layers
    :param service: SensorObservationService() type object of request
    :param procedures: List of queried procedures (observation providors)
    :param target:
    """
    points = dict()
    free_cat = 1

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
    output_format = service.get_operation_by_name('DescribeSensor').parameters[
        'outputFormat']['values'][0]

    if procedures:
        procedures = procedures.split(',')
    else:
        procedures = service.offerings[off_idx].procedures

    for proc in procedures:
        response = service.describe_sensor(procedure=proc,
                                           outputFormat=output_format)
        root = SensorML(response)
        system = root.members[0]
        name = system.name
        desc = system.description
        keywords = ','.join(system.keywords)
        sens_type = system.classifiers['Sensor Type'].value
        sys_type = system.classifiers['System Type'].value
        crs = int(system.location[0].attrib['srsName'].split(':')[-1])
        coords = system.location[0][0].text.replace('\n', '')
        sx = float(coords.split(',')[0])
        sy = float(coords.split(',')[1])
        sz = float(coords.split(',')[2])
        # Set source projection from SOS
        transform = soslib.get_transformation(crs, target)
        point = ogr.CreateGeometryFromWkt(
            'POINT ({} {} {})'.format(sx, sy, sz))
        point.Transform(transform)
        x = point.GetX()
        y = point.GetY()
        z = point.GetZ()
        if name not in points.keys():
            points.update({name: free_cat})
            point = Point(x, y, z)
            new.write(point, cat=free_cat, attrs=(
                      u'{}'.format(system.name),
                      system.description,
                      ','.join(system.keywords),
                      system.classifiers['Sensor Type'].value,
                      system.classifiers['System Type'].value,
                      crs,
                      float(coords.split(',')[0]),
                      float(coords.split(',')[1]),
                      float(coords.split(',')[2]),))
            free_cat += 1
    new.table.conn.commit()
    new.close(build=True)


def maps_rows_sensors(parsed_obs, offering, new, seconds_granularity,
                      target, epoch_s, epoch_e, i):
    """Import vectors with rows representing procedures.

    Layers represent output_offering_observedproperties and rows represent
    procedures

    :param parsed_obs: Observations for a given offering in geoJSON format
    :param offering: A collection of sensors used to conveniently group them up
    :param new: Given vector map which should be updated with new layers
    :param seconds_granularity: Granularity in seconds
    :param target: The target CRS for sensors
    :param epoch_s: time.mktime standardized timestamp of the beginning of obs
    :param epoch_e: time.mktime standardized timestamp of the end of obs
    :param i: Index of the first free layer
    """
    free_cat = 1

    for key, observation in parsed_obs.items():
        points = {}

        table_name = soslib.standardize_table_name(
            [options['output'], offering, key])

        data = json.loads(observation)
        # get the transformation between source and target crs
        crs = data['crs']
        crs = int(crs['properties']['name'].split(':')[-1])
        transform = soslib.get_transformation(crs, target)

        intervals = {}
        for seconds_stamp in range(epoch_s, epoch_e + 1, seconds_granularity):
            intervals.update({seconds_stamp: dict()})

        empty_procs = list()
        timestamp_pattern = 't%Y%m%dT%H%M%S'  # TODO: Timezone
        coords_dict = {}

        cols = [(u'cat', 'INTEGER PRIMARY KEY'), (u'name', 'VARCHAR')]

        if new.is_open() is True:
            # close without printing that crazy amount of messages
            new.close(build=False)
            run_command('v.build', quiet=True, map=options['output'])
            new.open('rw')
        else:
            new.open('w')

        for a in data['features']:
            name = a['properties']['name']
            empty = True

            if name not in points.keys():
                points.update({name: free_cat})

                # transform the geometry into the target crs
                sx, sy, sz = a['geometry']['coordinates']
                point = ogr.CreateGeometryFromWkt('POINT ({} {} {})'.format(
                    sx, sy, sz))
                point.Transform(transform)
                coords = (point.GetX(), point.GetY(), point.GetZ())

                coords_dict.update({free_cat: coords})
                free_cat += 1

            for timestamp, value in a['properties'].items():
                if timestamp != 'name':
                    if empty:
                        empty = False
                    observationstart_time = timestamp[:-4]
                    seconds_timestamp = int(time.mktime(
                        time.strptime(observationstart_time,
                                      timestamp_pattern)))
                    for interval in intervals.keys():
                        if interval <= seconds_timestamp < (
                                interval + seconds_granularity):
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
                # in value, there is name of the last proc
                empty_procs.append(value)

        if len(cols) > 2000:
            grass.warning(
                'Recommended number of columns is less than 2000, you have '
                'reached {}\nYou should set an event_time with a smaller range'
                ' or recompile SQLite limits as described at '
                'https://sqlite.org/limits.html'.format(len(cols)))

        link = Link(
            layer=i, name=table_name, table=table_name, key='cat',
            database='$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db',
            driver='sqlite')

        if new.is_open():
            new.close()

        new.open('rw')
        new.dblinks.add(link)
        new.table = new.dblinks[i - 1].table()
        new.table.create(cols)
        inserts = dict()

        new.close(build=False)
        run_command('v.build', quiet=True, map=options['output'])
        new.open('rw', layer=i)

        for cat, coords in coords_dict.items():
            new.write(Point(*coords), cat=cat)

        # create attr tab inserts for empty procs
        for emptyProc in empty_procs:
            insert = [None] * len(cols)
            insert[0] = points[emptyProc]
            insert[1] = emptyProc
            inserts.update({emptyProc: insert})

        # create attr tab inserts for procs with observations
        for interval in intervals.keys():
            if len(intervals[interval]) != 0:
                timestamp = datetime.datetime.fromtimestamp(
                    interval).strftime('t%Y%m%dT%H%M%S')

                for name, values in intervals[interval].items():
                    if options['method'] == 'average':
                        aggregated_value = sum(values) / len(values)
                    elif options['method'] == 'sum':
                        aggregated_value = sum(values)

                    if name not in inserts.keys():
                        insert = [None] * len(cols)
                        insert[0] = points[name]
                        insert[1] = name
                        insert[cols.index((timestamp,
                                           'DOUBLE'))] = aggregated_value
                        inserts.update({name: insert})
                    else:
                        inserts[name][cols.index(
                            (timestamp, 'DOUBLE'))] = aggregated_value

        for insert in inserts.values():
            new.table.insert(tuple(insert))
            new.table.conn.commit()

        i += 1

    # to avoid printing that crazy amount of messages
    new.close(build=False)
    run_command('v.build', quiet=True, map=options['output'])


def maps_rows_timestamps(parsed_obs, offering, new, seconds_granularity,
                         target, obs_props, epoch_s, epoch_e, i):
    """Import vectors with rows representing timestamps.

    Layers represent output_offering_procedure and rows representing timestamps

    :param parsed_obs: Observations for a given offering in geoJSON format
    :param offering: A collection of sensors used to conveniently group them up
    :param new: Given vector map which should be updated with new layers
    :param seconds_granularity: Granularity in seconds
    :param target: The target CRS for sensors
    :param obs_props: Oberved properties
    :param epoch_s: time.mktime standardized timestamp of the beginning of obs
    :param epoch_e: time.mktime standardized timestamp of the end of obs
    :param i: Index of the first free layer
    """
    db = '$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db'

    points = dict()
    free_cat = 1

    for propIndex in range(len(obs_props)):
        obs_props[propIndex] = soslib.standardize_table_name(
            [obs_props[propIndex]])

    for key, observation in parsed_obs.items():
        print('Working on the observed property {}'.format(key))
        key = soslib.standardize_table_name([key])

        data = json.loads(observation)
        # get the transformation between source and target crs
        crs = data['crs']
        crs = int(crs['properties']['name'].split(':')[-1])
        transform = soslib.get_transformation(crs, target)

        empty_procs = list()
        timestamp_pattern = 't%Y%m%dT%H%M%S'  # TODO: Timezone
        cur_layer = i

        cols = [(u'connection', 'INTEGER'), (u'timestamp', 'VARCHAR')]
        for obsProp in obs_props:
            cols.append((u'{}'.format(obsProp), 'DOUBLE'))

        if new.is_open() is True:
            # close without printing that crazy amount of messages
            new.close(build=False)
            run_command('v.build', quiet=True, map=options['output'])
            new.open('rw')
        else:
            new.open('w')

        for a in data['features']:
            name = a['properties']['name']

            table_name = soslib.standardize_table_name(
                [options['output'], offering, name])

            intervals = {}
            for seconds_stamp in range(epoch_s, epoch_e + 1,
                                       seconds_granularity):
                intervals.update({seconds_stamp: dict()})

            empty = True

            for timestamp, value in a['properties'].items():
                if timestamp != 'name':
                    if empty:
                        empty = False
                    observationstart_time = timestamp[:-4]
                    seconds_timestamp = int(time.mktime(
                        time.strptime(observationstart_time,
                                      timestamp_pattern)))
                    for interval in intervals.keys():
                        if interval <= seconds_timestamp < (
                                interval + seconds_granularity):
                            if name in intervals[interval].keys():
                                intervals[interval][name].append(float(value))
                            else:
                                intervals[interval].update(
                                    {name: [float(value)]})
                            break

            if empty:
                # in value, there is name of the last proc
                empty_procs.append(value)

            if new.is_open() is True:
                # close without printing that crazy amount of messages
                new.close(build=False)
                run_command('v.build', quiet=True, map=options['output'])
            new.open('rw')

            yet_existing = False
            if not new.dblinks.by_name(table_name):
                link = Link(
                    layer=cur_layer, name=table_name, table=table_name,
                    key='connection',
                    database=db,
                    driver='sqlite')
                new.dblinks.add(link)
                new.table = new.dblinks[cur_layer - 1].table()
                new.table.create(cols)
            else:
                yet_existing = True

            # open the right layer
            new.close(build=False)
            run_command('v.build', quiet=True, map=options['output'])
            new.open('rw', layer=cur_layer)

            if name not in points.keys():
                points.update({name: free_cat})

                # transform the geometry into the target crs
                sx, sy, sz = a['geometry']['coordinates']
                point = ogr.CreateGeometryFromWkt('POINT ({} {} {})'.format(
                    sx, sy, sz))
                point.Transform(transform)
                coords = (point.GetX(), point.GetY(), point.GetZ())

                new.write(Point(*coords), cat=free_cat)
                free_cat += 1

            inserts = dict()

            # create attr tab inserts for empty procs
            for emptyProc in empty_procs:
                insert = [None] * len(cols)
                insert[0] = points[emptyProc]
                insert[1] = emptyProc
                inserts.update({emptyProc: insert})

            # create attr tab inserts for procs with observations
            for interval in intervals.keys():
                if len(intervals[interval]) != 0:
                    timestamp = datetime.datetime.fromtimestamp(
                        interval).strftime('t%Y%m%dT%H%M%S')
                    for name, values in intervals[interval].items():
                        if options['method'] == 'average':
                            aggregated_value = sum(values) / len(values)
                        elif options['method'] == 'sum':
                            aggregated_value = sum(values)

                        if yet_existing:
                            a = read_command(
                                'db.select',
                                sql='SELECT COUNT(*) FROM {} WHERE '
                                    'timestamp="{}"'.format(table_name,
                                                            timestamp)
                            )
                            if a.split('\n')[1] != '0':
                                run_command(
                                    'db.execute',
                                    sql='UPDATE {} SET {}={} WHERE '
                                        'timestamp="{}";'.format(
                                            table_name, key, aggregated_value,
                                            timestamp))
                                continue

                        # if name not in inserts.keys():
                        insert = [None] * len(cols)
                        insert[0] = points[name]
                        insert[1] = timestamp
                        insert[cols.index(
                            (key, 'DOUBLE'))] = aggregated_value

                        new.table.insert(tuple(insert))

                new.table.conn.commit()

            cur_layer += 1

    new.close()


if __name__ == "__main__":

    options, flags = parser()

    try:
        import soslib
    except ImportError:
        grass.fatal("Cannot import Python module soslib containing "
                    "SOS-connected functions necessary to run this module.")

    main()
