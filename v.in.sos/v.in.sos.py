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

    new = VectorTopo(options['output'])
    new.open('w')
    new.close()

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

        if options['version'] in ['1.0.0', '1.0'] and str(options['response_format']) == 'text/xml;subtype="om/1.0.0"':
            for property in options['observed_properties'].split(','):
                parsed_obs.update({property: xml2geojson(obs, property)})
        elif str(options['response_format']) == 'application/json':
            for property in options['observed_properties'].split(','):
                parsed_obs.update({property: json2geojson(obs, property)})

        create_maps(parsed_obs, off, layerscount, new)
        layerscount += len(parsed_obs)

    return 0


def get_description(service):
    if flags['o'] is True:
        print('\nSOS offerings:')
        for offering in service.offerings:
            print(offering.name)

    if flags['v'] is True:
        print('\nObserved properties of %s offering:' % options['offering'])
        for observed_property in service[
            options['offering']].observed_properties:
            print(observed_property)

    if flags['p'] is True:
        print('\nProcedures of %s offering:' % options['offering'])
        for procedure in service[options['offering']].procedures:
            print(procedure)

    if flags['t'] is True:
        print('\nBegin timestamp, end timestamp of %s offering:' % options[
            'offering'])
        print('%s, %s' % (service[options['offering']].begin_position,
                          service[options['offering']].end_position))

    sys.exit(0)


def handle_not_given_options(service, offering=None):
    if offering == '' or options['output'] == '':
        if sys.version >= (3, 0):
            sys.tracebacklimit = None
        else:
            sys.tracebacklimit = 0
        raise AttributeError(
            'You have to define any flag or parameters output and offering')

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

    for key, observation in parsed_obs.iteritems():
        new.open('rw')
        tableName = '%s_%s' % (offering, key)
        if ':' in tableName:
            tableName = '_'.join(tableName.split(':'))
        if '-' in tableName:
            tableName = '_'.join(tableName.split('-'))
        if '.' in tableName:
            tableName = '_'.join(tableName.split('.'))

        data = json.loads(observation)

        points = list()
        for a in data['features']:
            points.append(Point(*a['geometry']['coordinates']))
            new.write(Point(*a['geometry']['coordinates']))

        link = Link(layer=i, name=tableName, table=tableName, key='cat')
        new.dblinks.add(link)

        cols = [(u'cat', 'INTEGER PRIMARY KEY')]
        for a in data['features']:
            for b in a['properties'].keys():
                if b != 'name':
                    cols.append((u'%s' % b, 'VARCHAR'))
                elif (u'name', 'VARCHAR') not in cols:
                    cols.append((u'%s' % b, 'VARCHAR'))

        new.table = new.dblinks.by_layer(i).table()
        new.table.create(cols)
        index = 1
        for a in data['features']:
            for item, value in a['properties'].iteritems():
                if item != 'name':
                    insert = (index,)
                    for b in range(1,len(cols)):
                        if cols[b][0] == 'name':
                            insert += (a['properties']['name'],)
                        elif cols[b][0] != item:
                            insert += ('',)
                        else:
                            insert += (value,)
                    index += 1

                    new.table.insert([insert], many=True)

        new.table.conn.commit()
        new.close()


        # temp = open(grass.tempfile(), 'r+')
        # temp.write(observation)
        # temp.seek(0)
        #
        # try:
        #     run_command('g.findfile',
        #                 element='vector',
        #                 file=options['output'])
        #
        #     run_command('db.in.ogr',
        #                 input=temp.name,
        #                 output=tableName,
        #                 key='id',
        #                 overwrite=True,
        #                 quiet=True)
        #     run_command('v.db.connect',
        #                 map=options['output'],
        #                 table=tableName,
        #                 layer=i,
        #                 key='id',
        #                 flags='o')
        # except:
        #     try:
        #         run_command('db.execute',
        #                     sql='DROP TABLE %s' % options['output'].split('@')[0])
        #     except:
        #         pass
        #
        #     run_command('v.in.ogr',
        #                 input=temp.name,
        #                 output=options['output'],
        #                 flags='o',
        #                 quiet=True)
        #
        #     run_command('v.db.addcolumn',
        #                 map=options['output'],
        #                 columns='id integer')
        #     run_command('v.db.update',
        #                 map=options['output'],
        #                 column='id',
        #                 query_column='cat')
        #
        # temp.close()


        i = i+1


if __name__ == "__main__":
    options, flags = parser()
    main()
