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

def cleanup():
    pass


def main():
    fl = ''

    for f, i in flags.iteritems():
        if i is True:
            fl += f

    run_command('v.in.sos', flags=fl, **options)
    # TODO: Check if there was printed description or computed vectors

    layers = get_map_layers()

    create_maps()

    return 0


def get_map_layers():
    service = SensorObservationService(options['url'],
                                       version=options['version'])
    layersList = list()

    options['event_time'] = 'T'.join(options['event_time'].split(' '))

    for off in options['offering'].split(','):
        handle_not_given_options(service, off)
        for obs in options['observed_properties'].split(','):
            layersList.append('{}_{}_{}'.format(options['output'], off, obs))

    i = 0
    for layer in layersList:
        if ':' in layer:
            layer = '_'.join(layer.split(':'))
        if '-' in layer:
            layer = '_'.join(layer.split('-'))
        if '.' in layer:
            layer = '_'.join(layer.split('.'))

        layersList[i] = layer
        i += 1

    return layersList


def handle_not_given_options(service, offering=None):
    # DUPLICATED: Also in v.in.sos
    if options['procedure'] == '':
        options['procedure'] = None

    if options['observed_properties'] == '':
        for observed_property in service[offering].observed_properties:
            options['observed_properties'] += '%s,' % observed_property
        options['observed_properties'] = options['observed_properties'][:-1]

    if options['event_time'] == '':
        options['event_time'] = '%s/%s' % (service[offering].begin_position, service[offering].end_position)


def create_maps():
    print('TODO: Use v.to.rast and delete vector maps')


if __name__ == "__main__":
    options, flags = parser()
    main()
