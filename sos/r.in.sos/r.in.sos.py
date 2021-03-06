#!  /usr/bin/env python3
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
#% key: s
#% description: Skip import of observation and import all procedures for offering
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
#%flag
#% key: k
#% description: Keep intermediates vector maps
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
import time
import datetime
import os
try:
    from owslib.sos import SensorObservationService
    from owslib.swe.sensor.sml import SensorML
    from osgeo import ogr
    from grass.script import parser, run_command, overwrite
    from grass.script import core as grass
    from grass.pygrass.vector import VectorTopo
    from grass.pygrass.vector.geometry import Point
    from grass.pygrass.vector.table import Link
    from grass.pygrass.utils import get_lib_path
except ImportError as e:
    sys.stderr.write(
        'Error importing internal libs. Did you run the script from GRASS '
        'GIS?\n')
    raise e

path = get_lib_path(modname='sos', libname='libsos')
if path is None:
    grass.script.fatal('Not able to find the sos library directory.')
sys.path.append(path)


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

    if options['resolution'] == '':
        a = grass.read_command('g.region', flags='gf')
        resolution = float(a.split('nsres=')[1].split(' ')[0])
        run_command(
            'g.message',
            flags='w',
            message='No resolution was setted. Using the resolution '
                    '{} (nres of your current setting).'.format(resolution))
    else:
        resolution = float(options['resolution'])

    if options['bbox'] != '':
        bbox = options['bbox'].split(',')
        run_command('g.region', n=float(bbox[0]), e=float(bbox[1]),
                    s=float(bbox[2]), w=float(bbox[3]),
                    res=resolution)
    else:
        grass.warning('You have not setted the bounding box. Bounding box will'
                      ' be automatically based on procedure geometries for '
                      'every map.')

    target = soslib.get_target_crs()

    for off in options['offering'].split(','):
        # TODO: Find better way than iteration (at best OWSLib upgrade)
        out = soslib.handle_not_given_options(
            service, off, options['procedure'], options['observed_properties'],
            options['event_time'])
        procedure, observed_properties, event_time = out

        if flags['s']:
            create_maps(_, off, _, resolution, _, service, target, procedure)
        else:
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
                if options['version'] in ['1.0.0', '1.0'] and \
                  options['response_format'] == 'text/xml;subtype="om/1.0.0"':
                    for prop in observed_properties:
                        parsed_obs.update(
                            {prop: soslib.xml2geojson(obs, prop)})
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

            create_maps(parsed_obs, off, seconds_granularity, resolution,
                        event_time, service, target)

    return 0


def create_maps(parsed_obs, offering, seconds_granularity, resolution,
                event_time, service, target, procedures=None):
    """Create raster maps.

    Maps represent offerings, observed props and procedures

    :param parsed_obs: Observations for a given offering in geoJSON format
    :param offering: A collection of sensors used to conveniently group them up
    :param seconds_granularity: Granularity in seconds
    :param resolution: 2D grid resolution for rasterization
    :param event_time: Timestamp of first/of last requested observation
    :param service: SensorObservationService() type object of request
    :param target:
    :param procedures: List of queried procedures (observation providors)
    """
    if flags['s']:
        maps_without_observations(offering, resolution, service, procedures,
                                  target)
    else:
        full_maps(parsed_obs, offering, seconds_granularity,
                  resolution, event_time, target)


def maps_without_observations(offering, resolution, service, procedures,
                              target):
    """Import just pixels/sensors without their observations.

    :param offering: A collection of sensors used to conveniently group them up
    :param resolution: 2D grid resolution for rasterization
    :param service: SensorObservationService() type object of request
    :param procedures: List of queried procedures (observation providors)
    :param target:
    """
    offs = [o.id for o in service.offerings]
    off_idx = offs.index(offering)
    output_format = service.get_operation_by_name('DescribeSensor').parameters[
        'outputFormat']['values'][0]

    if procedures:
        procedures = procedures.split(',')
    else:
        procedures = service.offerings[off_idx].procedures

    tempfile_path = grass.tempfile()
    n = None
    s = None
    e = None
    w = None

    with open(tempfile_path, 'w') as tempFile:
        for proc in procedures:
            response = service.describe_sensor(procedure=proc,
                                               output_format=output_format)
            root = SensorML(response)
            system = root.members[0]
            crs = int(system.location[0].attrib['srsName'].split(':')[-1])
            coords = system.location[0][0].text.replace('\n', '')
            sx = float(coords.split(',')[0])
            sy = float(coords.split(',')[1])
            sz = float(coords.split(',')[2])
            transform = soslib.get_transformation(crs, target)
            point = ogr.CreateGeometryFromWkt('POINT ({} {} {})'.format(sx,
                                                                        sy,
                                                                        sz))
            point.Transform(transform)
            x = point.GetX()
            y = point.GetY()
            z = point.GetZ()
            tempFile.write('{} {} {}\n'.format(x, y, z))

            if not n:
                n = y + resolution / 2
                s = y - resolution / 2
                e = x + resolution / 2
                w = x - resolution / 2
            else:
                if y >= n:
                    n = y + resolution / 2
                if y <= s:
                    s = y - resolution / 2
                if x >= e:
                    e = x + resolution / 2
                if x <= w:
                    w = x - resolution / 2

    run_command('g.region', n=n, s=s, w=w, e=e, res=resolution)
    run_command('r.in.xyz',
                input=tempfile_path,
                separator='space',
                output='{}_{}'.format(options['output'], offering))


def full_maps(parsed_obs, offering, seconds_granularity, resolution,
              event_time, target):
    """Create raster maps.

    Maps represent represent offerings, observed props and procedures

    :param parsed_obs: Observations for a given offering in geoJSON format
    :param offering: A collection of sensors used to conveniently group them up
    :param seconds_granularity: Granularity in seconds
    :param resolution: 2D grid resolution for rasterization
    :param event_time: Timestamp of first/of last requested observation
    :param target:
    """
    timestamp_pattern = '%Y-%m-%dT%H:%M:%S'  # TODO: Timezone
    start_time = event_time.split('+')[0]
    epoch_s = int(time.mktime(time.strptime(start_time, timestamp_pattern)))
    end_time = event_time.split('+')[1].split('/')[1]
    epoch_e = int(time.mktime(time.strptime(end_time, timestamp_pattern)))

    for key, observation in parsed_obs.items():
        print('Creating raster maps for offering '
              '{}, observed property {}'.format(offering, key))

        data = json.loads(observation)
        crs = data['crs']
        crs = int(crs['properties']['name'].split(':')[-1])
        transform = soslib.get_transformation(crs, target)

        cols = [(u'cat', 'INTEGER PRIMARY KEY'), (u'name', 'VARCHAR'),
                (u'value', 'DOUBLE')]

        geometries = dict()
        intervals = {}
        for secondsStamp in range(epoch_s, epoch_e + 1, seconds_granularity):
            intervals.update({secondsStamp: dict()})

        timestamp_pattern = 't%Y%m%dT%H%M%S'  # TODO: Timezone

        for a in data['features']:
            name = a['properties']['name']

            sx, sy, sz = a['geometry']['coordinates']
            point = ogr.CreateGeometryFromWkt('POINT ({} {} {})'.format(sx,
                                                                        sy,
                                                                        sz))
            point.Transform(transform)
            coords = (point.GetX(), point.GetY(), point.GetZ())
            geometries.update({name: coords})

            for timestamp, value in a['properties'].items():
                if timestamp != 'name':
                    observation_start_time = timestamp[:-4]
                    seconds_timestamp = int(time.mktime(
                        time.strptime(observation_start_time,
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

        for interval in intervals.keys():
            if len(intervals[interval]) != 0:
                timestamp = datetime.datetime.fromtimestamp(
                    interval).strftime('t%Y%m%dT%H%M%S')

                table_name = '{}_{}_{}_{}'.format(options['output'],
                                                  offering, key,
                                                  timestamp)
                if ':' in table_name:
                    table_name = '_'.join(table_name.split(':'))
                if '-' in table_name:
                    table_name = '_'.join(table_name.split('-'))
                if '.' in table_name:
                    table_name = '_'.join(table_name.split('.'))

                new = VectorTopo(table_name)
                if overwrite() is True:
                    try:
                        new.remove()
                    except:
                        pass

                new.open(mode='w', layer=1, tab_name=table_name,
                         link_name=table_name, tab_cols=cols, overwrite=True)
                i = 0
                n = None
                s = None
                e = None
                w = None

                for procedure, values in intervals[interval].items():
                    if new.exist() is False:
                        i = 1
                    else:
                        i += 1

                    if options['method'] == 'average':
                        value = sum(values) / len(values)
                    elif options['method'] == 'sum':
                        value = sum(values)
                    # TODO: Other aggregations methods

                    new.write(Point(*geometries[procedure]),
                              cat=i,
                              attrs=(procedure, value,))

                    if options['bbox'] == '':
                        x, y, z = geometries[procedure]
                        if not n:
                            n = y + resolution / 2
                            s = y - resolution / 2
                            e = x + resolution / 2
                            w = x - resolution / 2
                        else:
                            if y >= n:
                                n = y + resolution / 2
                            if y <= s:
                                s = y - resolution / 2
                            if x >= e:
                                e = x + resolution / 2
                            if x <= w:
                                w = x - resolution / 2

                new.table.conn.commit()

                new.close(build=False)
                run_command('v.build', quiet=True, map=table_name)

                if options['bbox'] == '':
                    run_command('g.region', n=n, s=s, w=w, e=e, res=resolution)

                run_command('v.to.rast', input=table_name, output=table_name,
                            use='attr', attribute_column='value', layer=1,
                            type='point', quiet=True)

                if flags['k'] is False:
                    run_command('g.remove', 'f', type='vector',
                                name=table_name, quiet=True)


if __name__ == "__main__":
    options, flags = parser()

    try:
        import soslib
    except ImportError:
        grass.fatal("Cannot import Python module soslib containing "
                    "SOS-connected functions necessary to run this module.")

    main()
