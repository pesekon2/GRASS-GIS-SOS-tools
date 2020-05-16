#!/usr/bin/env python3
#
############################################################################
#
# MODULE:	    t.vect.in.sos
# AUTHOR(S):	Ondrej Pesek <pesej.ondrek@gmail.com>
# PURPOSE:	    Import data from SOS server as space temporal maps to GRASS
# COPYRIGHT:	(C) 2017 Ondrej Pesek and the GRASS Development Team
#
#		This program is free software under the GNU General
#		Public License (>=v2). Read the file COPYING that
#		comes with GRASS for details.
#
#############################################################################

#%module
#% description: Import data from SOS server as space temporal maps to GRASS.
#% keyword: vector
#% keyword: temporal
#% keyword: import
#% keyword: SOS
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
#%option
#% key: output
#% type: string
#% description: Prefix for output maps
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
#% description: Who provide the observations
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
from sqlite3 import OperationalError
import json
import tempfile
import time
import datetime
try:
    from owslib.sos import SensorObservationService
    from grass.script import parser, run_command, overwrite, pipe_command
    from grass.script import core as grass
    from grass.script import vector
    from grass.pygrass.vector import VectorTopo
    from grass.pygrass.vector.geometry import Point
    from grass.pygrass.vector.table import Link
    from grass.pygrass.utils import get_lib_path
    import grass.temporal as tgis
except ImportError as e:
    sys.stderr.write('Error importing internal libs. '
                     'Did you run the script from GRASS GIS?\n')
    raise e

path = get_lib_path(modname='sos', libname='libsos')
if path is None:
    grass.script.fatal('Not able to find the sos library directory.')
sys.path.append(path)
from soslib import *


def cleanup():
    pass


def main():
    parsed_obs = dict()

    service = SensorObservationService(options['url'],
                                       version=options['version'],
                                       username=options['username'],
                                       password=options['password'])

    if any(value is True and key in [
      'o', 'v', 'p', 't'] for key, value in flags.items()):
        get_description(service, options, flags)

    check_missing_params(options['offering'], options['output'])

    if options['granularity'] != '':
        import grass.temporal as tgis
        tgis.init()
        seconds_granularity = int(tgis.gran_to_gran(options['granularity'],
                                                    '1 second',
                                                    True))
    else:
        seconds_granularity = 1

    for off in options['offering'].split(','):
        # TODO: Find better way than iteration (at best OWSLib upgrade)
        procedure, observed_properties, event_time = handle_not_given_options(
            service, off, options['procedure'], options['observed_properties'],
            options['event_time'])

        try:
            obs = service.get_observation(
                offerings=[off],
                responseFormat=options['response_format'],
                observedProperties=observed_properties,
                procedure=procedure,
                eventTime=event_time,
                username=options['username'],
                password=options['password'])
        except:
            # TODO: catch errors properly (e.g. timeout)
            grass.fatal('Request did not succeed!')

        try:
            if options['version'] in ['1.0.0', '1.0'] and str(
              options['response_format']) == 'text/xml;subtype="om/1.0.0"':
                for prop in observed_properties:
                    parsed_obs.update({prop: xml2geojson(obs, prop)})
            elif str(options['response_format']) == 'application/json':
                for prop in observed_properties:
                    parsed_obs.update({prop: json2geojson(obs, prop)})
        except AttributeError:
            if sys.version_info[0] >= 3:
                sys.tracebacklimit = None
            else:
                sys.tracebacklimit = 0
            raise AttributeError('There is no data for at least one of your '
                                 'procedures, could  you change the time '
                                 'parameter, observed properties, '
                                 'procedures or offerings')

        create_maps(parsed_obs, off, seconds_granularity, event_time)

    return 0


def create_maps(parsed_obs, offering, seconds_granularity, event_time):
    """Create vector map representing offerings and observed properties.

    :param parsed_obs: Observations for a given offering in geoJSON format
    :param offering: A collection of sensors used to conveniently group them up
    :param seconds_granularity: Granularity in seconds
    :param event_time:
    """
    timestamp_pattern = '%Y-%m-%dT%H:%M:%S'  # TODO: Timezone
    start_time = event_time.split('+')[0]
    epoch_s = int(time.mktime(time.strptime(start_time, timestamp_pattern)))
    end_time = event_time.split('+')[1].split('/')[1]
    epoch_e = int(time.mktime(time.strptime(end_time, timestamp_pattern)))

    for key, observation in parsed_obs.items():

        run_command('g.message',
                    message='Creating vector maps for {}...'.format(key))

        map_name = '{}_{}_{}'.format(options['output'], offering, key)
        if ':' in map_name:
            map_name = '_'.join(map_name.split(':'))
        if '-' in map_name:
            map_name = '_'.join(map_name.split('-'))
        if '.' in map_name:
            map_name = '_'.join(map_name.split('.'))

        run_command('t.create',
                    output=map_name,
                    type='stvds',
                    title='Dataset for offering {} and observed '
                          'property {}'.format(offering, key),
                    description='Vector space time dataset')

        free_cat = 1
        points = dict()
        new = VectorTopo(map_name)
        if overwrite() is True:
            try:
                new.remove()
            except:
                pass

        data = json.loads(observation)

        cols = [(u'cat', 'INTEGER PRIMARY KEY'), (u'name', 'VARCHAR'),
                (u'value', 'DOUBLE')]

        intervals = {}
        for secondsStamp in range(epoch_s, epoch_e + 1, seconds_granularity):
            intervals.update({secondsStamp: dict()})

        timestamp_pattern = 't%Y%m%dT%H%M%S'  # TODO: Timezone

        for a in data['features']:
            name = a['properties']['name']
            if a['properties']['name'] not in points.keys():
                if new.is_open() is False:
                    new.open('w')
                points.update({a['properties']['name']: free_cat})
                new.write(Point(*a['geometry']['coordinates']))
                free_cat += 1

            for timestamp, value in a['properties'].items():
                if timestamp != 'name':
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

        if new.is_open():
            new.close(build=False)
            run_command('v.build', map=map_name, quiet=True)

        i = 1
        layers_timestamps = list()
        for interval in intervals.keys():
            if len(intervals[interval]) != 0:
                timestamp = datetime.datetime.fromtimestamp(
                    interval).strftime('t%Y%m%dT%H%M%S')
                table_name = '{}_{}_{}_{}'.format(options['output'], offering,
                                                  key, timestamp)
                if ':' in table_name:
                    table_name = '_'.join(table_name.split(':'))
                if '-' in table_name:
                    table_name = '_'.join(table_name.split('-'))
                if '.' in table_name:
                    table_name = '_'.join(table_name.split('.'))

                new.open('rw')
                db = '$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db'
                link = Link(layer=i, name=table_name, table=table_name,
                            key='cat', database=db, driver='sqlite')
                new.dblinks.add(link)
                new.table = new.dblinks[i-1].table()
                new.table.create(cols)

                i += 1
                layers_timestamps.append(timestamp)

                for name, values in intervals[interval].items():
                    if options['method'] == 'average':
                        aggregated_value = sum(values) / len(values)
                    elif options['method'] == 'sum':
                        aggregated_value = sum(values)

                    new.table.insert(tuple([points[name],
                                            name,
                                            aggregated_value]))
                    new.table.conn.commit()

                new.close(build=False)
                run_command('v.build', map=map_name, quiet=True)

        create_temporal(map_name, i, layers_timestamps)


def create_temporal(vector_map, layers_count, layers_timestamps):
    """Create stvds from given vector map.

    One layer represents one timestamp

    :param vector_map: Vector map used as the original for registration
    :param layers_count: Count of layers (timestamps) of a vector map
    :param layers_timestamps: List of timestamps used in the original
        vector map
    """
    run_command('g.message',
                message='Registering maps in the space time dataset...')

    for i in range(1, layers_count):
        layer_timestamp = '{}-{}-{} {}:{}'.format(
            layers_timestamps[i - 1][1:5], layers_timestamps[i - 1][5:7],
            layers_timestamps[i - 1][7:9], layers_timestamps[i - 1][10:12],
            layers_timestamps[i - 1][12:14])

        run_command('t.register',
                    type='vector',
                    input=vector_map,
                    maps='{}:{}'.format(vector_map, i),
                    start=layer_timestamp,
                    quiet=True)


if __name__ == "__main__":
    options, flags = parser()
    main()
