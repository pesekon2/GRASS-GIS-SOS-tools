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
import json
from sqlite3 import OperationalError
try:
    from owslib.sos import SensorObservationService
    from grass.script import parser, run_command
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

    if options['offering'] == '' or options['output'] == '':
        if sys.version >= (3, 0):
            sys.tracebacklimit = None
        else:
            sys.tracebacklimit = 0
        raise AttributeError("You have to define any flags or use 'output' and"
                             " 'offering' parameters to get the data")

    run_command('g.remove', 'f', type='vector',
                name=options['output'])
    new = VectorTopo(options['output'])

    for off in options['offering'].split(','):
        # TODO: Find better way than iteration (at best OWSLib upgrade)
        procedure, observed_properties, event_time = handle_not_given_options(
            service, off, options['procedure'], options['observed_properties'],
            options['event_time'])
        event_time = 'T'.join(event_time.split(' '))

        obs = service.get_observation(
            offerings=[off],
            responseFormat=options['response_format'],
            observedProperties=[observed_properties],
            procedure=procedure,
            eventTime=event_time,
            username=options['username'],
            password=options['password'])

        try:
            if options['version'] in ['1.0.0', '1.0'] and str(
              options['response_format']) == 'text/xml;subtype="om/1.0.0"':
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
            raise AttributeError(
                'There is no data, could you change the time parameter, '
                'observed properties, procedures or offerings')

        create_maps(parsed_obs, off, layerscount, new)
        layerscount += len(parsed_obs)
    return 0


def create_maps(parsed_obs, offering, layer, new):
    """
    Add layers representing offerings and observed properties to the vector map
    :param parsed_obs: Observations for a given offering in geoJSON format
    :param offering: A collection of sensors used to conveniently group them up
    :param layer: Count of yet existing layers in vector map
    :param new: Given vector map which should be updated with new layers
    """

    i = layer + 1
    points = dict()
    freeCat = 1

    for key, observation in parsed_obs.iteritems():

        tableName = '{}_{}_{}'.format(options['output'], offering, key)
        if ':' in tableName:
            tableName = '_'.join(tableName.split(':'))
        if '-' in tableName:
            tableName = '_'.join(tableName.split('-'))
        if '.' in tableName:
            tableName = '_'.join(tableName.split('.'))

        data = json.loads(observation)

        cols = [(u'cat', 'INTEGER PRIMARY KEY'), (u'name', 'VARCHAR')]
        for a in data['features']:
            for b in a['properties'].keys():
                if b != 'name' and (u'%s' % b, 'DOUBLE') not in cols:
                    cols.append((u'%s' % b, 'DOUBLE'))

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

        for a in data['features']:
            if a['properties']['name'] not in points.keys():
                if new.is_open() is False:
                    new.open('w')
                points.update({a['properties']['name']: freeCat})
                new.write(Point(*a['geometry']['coordinates']), cat=freeCat)
                freeCat += 1
        if new.is_open():
            new.close()
        new.open('rw')
        new.dblinks.add(link)
        new.table = new.dblinks[i - 1].table()
        new.table.create(cols)
        for a in data['features']:
            insert = [None] * len(cols)
            for item, value in a['properties'].iteritems():
                if item != 'name':
                    insert[cols.index((item, 'DOUBLE'))] = value
                else:
                    insert[cols.index((item, 'VARCHAR'))] = value

            insert[0] = points[a['properties']['name']]
            new.table.insert(tuple(insert))

            new.table.conn.commit()
        new.close(build=False)
        run_command('v.build', quiet=True, map=options['output'])

        i += 1


if __name__ == "__main__":
    options, flags = parser()
    main()
