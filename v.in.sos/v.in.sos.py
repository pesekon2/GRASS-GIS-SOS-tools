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
#% description: Exmaple: 2015-06-01T00:00:00+0200/2015-06-03T00:00:00+0200
#% required: no
#% guisection: Request
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
from owslib.sos import SensorObservationService
from grass.script import parser, run_command
from grass.script import core as grass
from grass.pygrass.vector import VectorTopo
from grass.pygrass.vector.geometry import Point
from grass.pygrass.vector.table import Link
from sqlite3 import OperationalError
import json

sys.path.append('/home/ondrej/workspace/GRASS-GIS-SOS-tools/format_conversions')
# TODO: Incorporate format conversions into OWSLib and don't use absolute path
from xml2geojson import xml2geojson
from json2geojson import json2geojson


def cleanup():
    pass


def main():
    parsed_obs = dict()
    layerscount = 0

    service = SensorObservationService(options['url'],
                                       version=options['version'])

    if any(flags.itervalues()):
        get_description(service)

    if options['offering'] == '' or options['output'] == '':
        if sys.version >= (3, 0):
            sys.tracebacklimit = None
        else:
            sys.tracebacklimit = 0
        raise AttributeError(
            "You have to define any flags or use 'output' and 'offering' parameters to get the data")

    new = VectorTopo(options['output'])
    new.open('w')

    for off in options['offering'].split(','):
        # TODO: Find better way than iteration (at best OWSLib upgrade)
        handle_not_given_options(service, off)
        options['event_time'] = 'T'.join(options['event_time'].split(' '))

        obs = service.get_observation(offerings=[off],
                                      responseFormat=options['response_format'],
                                      observedProperties=[options['observed_properties']],
                                      procedure=options['procedure'],
                                      eventTime=options['event_time'],
                                      username=options['username'],
                                      password=options['password'])

        try:
            if options['version'] in ['1.0.0', '1.0'] and str(options['response_format']) == 'text/xml;subtype="om/1.0.0"':
                for property in options['observed_properties'].split(','):
                    parsed_obs.update({property: xml2geojson(obs, property)})
            elif str(options['response_format']) == 'application/json':
                for property in options['observed_properties'].split(','):
                    parsed_obs.update({property: json2geojson(obs, property)})
        except AttributeError:
            if sys.version >= (3, 0):
                sys.tracebacklimit = None
            else:
                sys.tracebacklimit = 0
            new.close(build=False)
            new.remove()
            raise AttributeError('There is no data, could you change the time parameter, observed properties, procedures or offerings')

        create_maps(parsed_obs, off, layerscount, new)
        layerscount += len(parsed_obs)

    new.close()

    return 0


def get_description(service):
    if flags['o'] is True:
        if flags['g'] is False:
            print('\nSOS offerings:')
        for offering in service.offerings:
            print(offering.name)

    if flags['v'] is True:
        if flags['g'] is False:
            print('\nObserved properties of '
                  '{} offering:'.format(options['offering']))
        for observed_property in service[
            options['offering']].observed_properties:
            print(observed_property)

    if flags['p'] is True:
        if flags['g'] is False:
            print('\nProcedures of {} offering:'.format(options['offering']))
        for procedure in service[options['offering']].procedures:
            print(procedure)

    if flags['t'] is True:
        if flags['g'] is False:
            print('\nBegin timestamp, end timestamp of '
                  '{} offering:'.format(options['offering']))
            print('{}, {}'.format(service[options['offering']].begin_position,
                                  service[options['offering']].end_position))
        else:
            print('start_time={}'.format(service[options['offering']].begin_position))
            print('end_time={}'.format(service[options['offering']].end_position))

    sys.exit(0)


def handle_not_given_options(service, offering=None):
    if options['procedure'] == '':
        options['procedure'] = None

    if options['observed_properties'] == '':
        for observed_property in service[offering].observed_properties:
            options['observed_properties'] += '%s,' % observed_property
        options['observed_properties'] = options['observed_properties'][:-1]

    if options['event_time'] == '':
        options['event_time'] = '%s/%s' % (service[offering].begin_position, service[offering].end_position)


def create_maps(parsed_obs, offering, layer, new):
    i = layer + 1
    points = list()

    for key, observation in parsed_obs.iteritems():

        tableName = '{}_{}_{}'.format(options['output'], offering, key)
        if ':' in tableName:
            tableName = '_'.join(tableName.split(':'))
        if '-' in tableName:
            tableName = '_'.join(tableName.split('-'))
        if '.' in tableName:
            tableName = '_'.join(tableName.split('.'))

        data = json.loads(observation)

        for a in data['features']:
            if [a['geometry']['coordinates']] not in points:
                points.append([Point(*a['geometry']['coordinates'])])
                new.write(Point(*a['geometry']['coordinates']))

        link = Link(layer=i, name=tableName, table=tableName, key='cat')
        new.dblinks.add(link)

        cols = [(u'cat', 'INTEGER PRIMARY KEY'), (u'name', 'VARCHAR')]
        for a in data['features']:
            for b in a['properties'].keys():
                if b != 'name':
                    cols.append((u'%s' % b, 'DOUBLE'))

        if len(cols) > 2000:
            grass.warning(
                'Recommended number of columns is less than 2000, you have '
                'reached {}\nYou should set an event_time with a smaller range '
                'or recompile SQLite limits as  described at '
                'https://sqlite.org/limits.html'.format(len(cols)))

        new.table = new.dblinks.by_layer(i).table()
        new.table.create(cols)

        index = 1
        for a in data['features']:
            insert = [''] * len(cols)
            for item, value in a['properties'].iteritems():
                if item != 'name':
                    insert[cols.index((item, 'DOUBLE'))] = value
                else:
                    insert[cols.index((item, 'VARCHAR'))] = value


            insert[0] = index
            index += 1
            insert = tuple(insert)
            try:
                new.table.insert([insert], many=True)
            except OperationalError:
                raise OperationalError(
                    'You have reached maximum number of columns. You should '
                    'set an event_time with a smaller range or recompile '
                    'SQLite limits as described at '
                    'https://sqlite.org/limits.html'.format(len(cols)))

        new.table.conn.commit()

        i = i+1


if __name__ == "__main__":
    options, flags = parser()
    main()
