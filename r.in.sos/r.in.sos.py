#!/usr/bin/env python
#
############################################################################
#
# MODULE:	    r.in.sos
# AUTHOR(S):	Ondrej Pesek <pesej.ondrek@gmail.com>
# PURPOSE:	    Import data from SOS server as raster maps to GRASS GIS
# COPYRIGHT:	(C) 2017 Ondrej Pesek and the GRASS Development Team
#
#		This program is free software under the GNU General
#		Public License (>=v2). Read the file COPYING that
#		comes with GRASS for details.
#
#############################################################################

#%module
#% description: Import data from SOS server as raster maps to GRASS GIS.
#% keyword: raster
#% keyword: import
#% keyword: SOS
#%end
#%flag
#% key: v
#% description: Print observed properties for given url and offering
#% guisection: SOS description
#%end
#%flag
#% key: o
#% description: Print offerings for given url
#% guisection: SOS description
#%end
#%flag
#% key: p
#% description: Print procedures for given url and offering
#% guisection: SOS description
#%end
#%flag
#% key: t
#% description: Print begin and end timestamps for given url and offering
#% guisection: SOS description
#%end
#%flag
#% key: g
#% description: Print informations in shell script style
#% guisection: SOS description
#%end
#%flag
#% key: f
#% description: Force deletion of created intermediates vector maps
#%end
#%option
#% key: url
#% type: string
#% description: Base URL starting with 'http' and ending in '?'
#% required: yes
#%end
#%option
#% key: output
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
#% type: integer
#% label: Granularity used to aggregate data
#% description: If not given, all data for event_time will be returned
#% required: no
#% guisection: Data
#%end
#%option
#% key: granularity_units
#% type: string
#% label: Unit must be set in case of granularity input
#% options: years, months, days, hours, minutes, seconds
#% required: no
#% guisection: Data
#%end
#%option
#% key: aggregation
#% type: string
#% label: Aggregation used in case of granularity
#% options: mean, sum
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
import time, datetime
try:
    from owslib.sos import SensorObservationService
    from grass.script import parser, run_command, overwrite
    from grass.script import core as grass
    from grass.pygrass.vector import VectorTopo
    from grass.pygrass.vector.geometry import Point
    from grass.pygrass.vector.table import Link
except ImportError as e:
    sys.stderr.write(
        'Error importing internal libs. Did you run the script from GRASS '
        'GIS?\n')
    raise(e)

sys.path.append('/home/ondrej/workspace/GRASS-GIS-SOS-tools/format_conversions')
# TODO: Incorporate format conversions into OWSLib and don't use absolute path
from xml2geojson import xml2geojson
from json2geojson import json2geojson


def cleanup():
    pass


def main():
    parsed_obs = dict()
    service = SensorObservationService(options['url'],
                                       version=options['version'])

    if any(value is True and key in [
      'o', 'v', 'p', 't'] for key, value in flags.iteritems()):
        get_description(service)

    if options['offering'] == '' or options['output'] == '':
        if sys.version >= (3, 0):
            sys.tracebacklimit = None
        else:
            sys.tracebacklimit = 0
        raise AttributeError(
            "You have to define any flags or use 'output' and 'offering' "
            "parameters to get the data")

    if options['granularity'] != '':
        secondsGranularity = get_seconds_granularity()
    else:
        secondsGranularity = 1

    for off in options['offering'].split(','):
        # TODO: Find better way than iteration (at best OWSLib upgrade)
        procedure, observed_properties, event_time = handle_not_given_options(
            service, off)
        event_time = 'T'.join(event_time.split(' '))

        obs = service.get_observation(
            offerings=[off], responseFormat=options['response_format'],
            observedProperties=[observed_properties], procedure=procedure,
            eventTime=event_time, username=options['username'],
            password=options['password'])

        try:
            if options['version'] in ['1.0.0', '1.0'] and \
              str(options['response_format']) == 'text/xml;subtype="om/1.0.0"':
                for property in observed_properties.split(','):
                    parsed_obs.update({property: xml2geojson(obs, property)})
            elif str(options['response_format']) == 'application/json':
                for property in observed_properties.split(','):
                    parsed_obs.update({property: json2geojson(obs, property)})
        except AttributeError:
            if sys.version >= (3, 0):
                sys.tracebacklimit = None
            else:
                sys.tracebacklimit = 0
            raise AttributeError('There is no data, could you change the time '
                                 'parameter, observed properties, procedures '
                                 'or offerings')

        create_maps(parsed_obs, off, secondsGranularity)

    return 0


def get_description(service):
    # DUPLICATED: Also in v.in.sos
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


def get_seconds_granularity():
    """
    transform given granularity from given format into number of seconds
    :return secondsGranularity: Number of seconds defining granularity
    """

    if options['granularity_units'] == 'seconds':
        secondsGranularity = int(options['granularity'])
    elif options['granularity_units'] == 'minutes':
        secondsGranularity = int(options['granularity']) * 60
    elif options['granularity_units'] == 'hours':
        secondsGranularity = int(options['granularity']) * 3600
    elif options['granularity_units'] == 'days':
        secondsGranularity = int(options['granularity']) * 86400
    elif options['granularity_units'] == 'months':
        # TODO: Make more month depending
        secondsGranularity = int(options['granularity']) * 2592000
    elif options['granularity_units'] == 'minutes':
        secondsGranularity = int(options['granularity']) * 31556926

    return secondsGranularity


def handle_not_given_options(service, offering=None):
    # DUPLICATED: Also in v.in.sos
    """
    If there are not given some options, use the full scale
    :param service: Service which we are requesting parameters for
    :param offering: A collection of sensors used to conveniently group them up
    :return procedure: Who provide the observations (mostly the sensor)
    :return observed_properties: The phenomena that are observed
    :return event_time: Timestamp of first,last requested observation
    """

    if options['procedure'] == '':
        procedure = None
    else:
        procedure = options['procedure']

    if options['observed_properties'] == '':
        observed_properties = ''
        for observed_property in service[offering].observed_properties:
            observed_properties += '{},'.format(observed_property)
        observed_properties = observed_properties[:-1]
    else:
        observed_properties = options['observed_properties']

    if options['event_time'] == '':
        beginTimestamp = str(service[offering].begin_position)
        beginTimestamp = 'T'.join(beginTimestamp.split(' '))
        endTimestamp = str(service[offering].end_position)
        endTimestamp = 'T'.join(endTimestamp.split(' '))
        event_time = '{}/{}'.format(beginTimestamp, endTimestamp)
    else:
        event_time = options['event_time']

    return procedure, observed_properties, event_time


def create_maps(parsed_obs, offering, secondsGranularity):
    """
    Create raster maps representing offerings, observed props and procedures
    :param parsed_obs: Observations for a given offering in geoJSON format
    :param offering: A collection of sensors used to conveniently group them up
    :param secondsGranularity: Granularity in seconds
    """

    timestampPattern = '%Y-%m-%dT%H:%M:%S' # TODO: Timezone
    startTime = options['event_time'].split('+')[0]
    epochS = int(time.mktime(time.strptime(startTime, timestampPattern)))
    endTime = options['event_time'].split('+')[1].split('/')[1]
    epochE = int(time.mktime(time.strptime(endTime, timestampPattern)))

    for key, observation in parsed_obs.iteritems():
        data = json.loads(observation)

        cols = [(u'cat', 'INTEGER PRIMARY KEY'), (u'name', 'VARCHAR'),
                (u'value', 'DOUBLE')]

        geometries = dict()
        intervals = {}
        for secondsStamp in range(epochS, epochE + 1, secondsGranularity):
            intervals.update({secondsStamp: dict()})

        timestampPattern = 't%Y%m%dT%H%M%S'  # TODO: Timezone

        for a in data['features']:
            name = a['properties']['name']
            geometries.update({name: a['geometry']['coordinates']})

            for timestamp, value in a['properties'].iteritems():
                if timestamp != 'name':
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

        for interval in intervals.keys():
            if len(intervals[interval]) != 0:
                timestamp = datetime.datetime.fromtimestamp(
                    interval).strftime('t%Y%m%dT%H%M%S')

                tableName = '{}_{}_{}_{}'.format(options['output'],
                                                 offering, key,
                                                 timestamp)
                if ':' in tableName:
                    tableName = '_'.join(tableName.split(':'))
                if '-' in tableName:
                    tableName = '_'.join(tableName.split('-'))
                if '.' in tableName:
                    tableName = '_'.join(tableName.split('.'))

                new = VectorTopo(tableName)
                if overwrite() is True:
                    try:
                        new.remove()
                    except:
                        pass

                new.open(mode='w', layer=1, tab_name=tableName,
                         link_name=tableName, tab_cols=cols, overwrite=True)
                i = 1
                for procedure, values in intervals[interval].iteritems():
                    if new.exist() is False:
                        i = 1
                    else:
                        i += 1

                    if options['aggregation'] == 'mean':
                        value = sum(values) / len(values)
                    elif options['aggregation'] == 'sum':
                        value = sum(values)
                    # TODO: Other aggregations

                    new.write(Point(*geometries[procedure]),
                              cat=i,
                              attrs=(procedure, value,))

                new.table.conn.commit()

                new.close(build=False)
                run_command('v.build', quiet=True, map=tableName)

                run_command('g.region', vect=tableName)
                run_command('v.to.rast', input=tableName, output=tableName,
                            use='attr', attribute_column='value', layer=1,
                            label_column='name', type='point',
                            quiet=True)

                if flags['f'] is True:
                    run_command('g.remove', 'f', type='vector',
                                name=tableName, quiet=True)


if __name__ == "__main__":
    options, flags = parser()
    main()
