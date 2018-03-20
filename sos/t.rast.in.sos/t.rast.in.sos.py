#!/usr/bin/env python
#
############################################################################
#
# MODULE:	    t.rast.in.sos
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
#% description: Import data from SOS server as space temporal maps to GRASS.
#% keyword: raster
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
#% required: yes
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
#% key: bbox
#% type: string
#% label: Bounding box
#% description: n,e,s,w
#% guisection: Data
#%end
#%option
#% key: resolution
#% type: string
#% label: 2D grid resolution (north-south and east-west)
#% guisection: Data
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
    from grass.script import parser, run_command, overwrite
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
    raise(e)

path = get_lib_path(modname='sos', libname='libsos')
if path is None:
    grass.script.fatal('Not able to find the sos library directory.')
sys.path.append(path)
from soslib import xml2geojson, json2geojson
from soslib import handle_not_given_options


def cleanup():
    pass


def main():

    fl = str()
    for f, val in flags.iteritems():
        if val is True:
            fl += f

    try:
        run_command('r.in.sos', flags=fl, **options)
    except:
        return 0
    if any(value is True and key in [
           'o', 'v', 'p', 't'] for key, value in flags.iteritems()):
        return 0

    service = SensorObservationService(options['url'],
                                       version=options['version'],
                                       username=options['username'],
                                       password=options['password'])

    for off in options['offering'].split(','):
        procedure, observed_properties, event_time = handle_not_given_options(
            service, off, options['procedure'], options['observed_properties'],
            options['event_time'])
        for observedProperty in observed_properties:
            mapName = '{}_{}_{}'.format(options['output'], off,
                                        observedProperty)
            if ':' in mapName:
                mapName = '_'.join(mapName.split(':'))
            if '-' in mapName:
                mapName = '_'.join(mapName.split('-'))
            if '.' in mapName:
                mapName = '_'.join(mapName.split('.'))

            mapsListFile = get_maps(mapName)
            create_temporal(mapsListFile, mapName)

    return 0


def get_maps(mapName):
    """
    Get the list of maps created during r.in.sos
    :param mapName: Prefix of raster maps names (name without timestamp)
    :return tmpFile: Temporary file containing the intermediate raster maps
    """

    tmpFile = grass.tempfile()
    run_command('g.list', type='raster',
                pattern='{}_*'.format(mapName),
                output=tmpFile, overwrite=True)

    return tmpFile


def create_temporal(mapsListFile, mapName):
    """
    Create strds from given raster maps where every raster map is timestamped
    :param mapsListFile: Temporary file containing names of raster maps
    :param mapName: Name for the output strds
    """

    run_command('t.create',
                output=mapName,
                type='strds',
                title='Dataset for offering {} and observed '
                      'property {}'.format(mapName.split('_')[1],
                                           '_'.join(mapName.split('_')[2:])),
                description='Raster space time dataset')

    with open(mapsListFile, 'r') as maps:
        for rasterMap in maps.readlines():
            a = rasterMap.split('t')[-1]
            mapTimestamp = '{}-{}-{} {}:{}'.format(a[0:4], a[4:6], a[6:8],
                                                   a[9:11], a[11:13])
            run_command('t.register',
                        type='raster',
                        input=mapName,
                        maps='{}'.format(rasterMap.strip()),
                        start=mapTimestamp,
                        quiet=True)


if __name__ == "__main__":
    options, flags = parser()
    main()
