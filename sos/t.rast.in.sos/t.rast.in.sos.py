#!/usr/bin/env python3
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
    raise e

path = get_lib_path(modname='sos', libname='libsos')
if path is None:
    grass.script.fatal('Not able to find the sos library directory.')
sys.path.append(path)


def cleanup():
    pass


def main():
    fl = str()
    for f, val in flags.items():
        if val is True:
            fl += f

    try:
        run_command('r.in.sos', flags=fl, **options)
    except:
        return 0
    if any(value is True and key in [
           'o', 'v', 'p', 't'] for key, value in flags.items()):
        return 0

    service = SensorObservationService(options['url'],
                                       version=options['version'],
                                       username=options['username'],
                                       password=options['password'])

    for off in options['offering'].split(','):
        out = soslib.handle_not_given_options(
            service, off, options['procedure'], options['observed_properties'],
            options['event_time'])
        procedure, observed_properties, event_time = out

        for observed_property in observed_properties:
            map_name = '{}_{}_{}'.format(options['output'], off,
                                         observed_property)
            if ':' in map_name:
                map_name = '_'.join(map_name.split(':'))
            if '-' in map_name:
                map_name = '_'.join(map_name.split('-'))
            if '.' in map_name:
                map_name = '_'.join(map_name.split('.'))

            maps_list_file = get_maps(map_name)
            create_temporal(maps_list_file, map_name)

    return 0


def get_maps(map_name):
    """Get the list of maps created during r.in.sos.

    :param map_name: Prefix of raster maps names (name without timestamp)
    :return tmp_file: Temporary file containing the intermediate raster maps
    """
    tmp_file = grass.tempfile()
    run_command('g.list', type='raster',
                pattern='{}_*'.format(map_name),
                output=tmp_file, overwrite=True)

    return tmp_file


def create_temporal(maps_list_file, map_name):
    """Create strds from given raster maps.

    Every raster map is timestamped

    :param maps_list_file: Temporary file containing names of raster maps
    :param map_name: Name for the output strds
    """
    run_command('t.create',
                output=map_name,
                type='strds',
                title='Dataset for offering {} and observed '
                      'property {}'.format(map_name.split('_')[1],
                                           '_'.join(map_name.split('_')[2:])),
                description='Raster space time dataset')

    with open(maps_list_file, 'r') as maps:
        for raster_map in maps.readlines():
            a = raster_map.split('t')[-1]
            map_timestamp = '{}-{}-{} {}:{}'.format(a[0:4], a[4:6], a[6:8],
                                                    a[9:11], a[11:13])
            run_command('t.register',
                        type='raster',
                        input=map_name,
                        maps='{}'.format(raster_map.strip()),
                        start=map_timestamp,
                        quiet=True)


if __name__ == "__main__":
    options, flags = parser()

    try:
        import soslib
    except ImportError:
        grass.fatal("Cannot import Python module soslib containing "
                    "SOS-connected functions necessary to run this module.")

    main()
